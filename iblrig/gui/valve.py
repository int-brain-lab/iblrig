import functools
import logging
from collections import OrderedDict
from datetime import date

import numpy as np
import pyqtgraph as pg
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QThreadPool
from pyqtgraph import PlotWidget
from serial import SerialException
from typing_extensions import override

from iblrig.gui.tools import Worker
from iblrig.gui.ui_valve import Ui_valve
from iblrig.hardware import Bpod
from iblrig.path_helper import save_pydantic_yaml
from iblrig.pydantic_definitions import HardwareSettings
from iblrig.scale import Scale
from iblrig.valve import Valve, ValveValues
from pybpodapi.exceptions.bpod_error import BpodErrorException

log = logging.getLogger(__name__)


class CalibrationPlot:
    def __init__(self, parent: PlotWidget, name: str, color: str, values: ValveValues | None = None):
        self._values = values if values is not None else ValveValues([], [])
        self._curve = pg.PlotCurveItem(name=name)
        self._curve.setPen(color, width=3)
        self._points = pg.ScatterPlotItem()
        self._points.setPen(color)
        self._points.setBrush(color)
        self._parent = parent
        parent.addItem(self._curve)
        parent.addItem(self._points)
        self.update()

    @property
    def values(self) -> ValveValues:
        return self._values

    @values.setter
    def values(self, values: ValveValues):
        self._values = values
        self.update()

    def update(self):
        self._points.setData(x=self.values.open_times_ms, y=self.values.volumes_ul)
        if len(self.values.open_times_ms) < 2:
            self._curve.setData(x=[], y=[])
        else:
            time_range = list(np.linspace(self.values.open_times_ms[0], self.values.open_times_ms[-1], 100))
            self._curve.setData(x=time_range, y=self.values.ms2ul(time_range))

    def clear(self):
        self.values.clear_data()
        self.update()


class ValveCalibrationDialog(QtWidgets.QDialog, Ui_valve):
    scale: Scale | None = None
    scale_initialized = QtCore.pyqtSignal(bool)
    scale_text_changed = QtCore.pyqtSignal(str)
    scale_stable_changed = QtCore.pyqtSignal(bool)
    drop_cleared = QtCore.pyqtSignal(int)
    tared = QtCore.pyqtSignal(bool)
    calibration_finished = QtCore.pyqtSignal()
    start_next_calibration = QtCore.pyqtSignal()
    _grams = float('nan')
    _stable = False
    _next_calibration_step = 1
    _next_calibration_time = float('nan')
    _scale_update_ms = 100
    _clear_drop_counter = 0

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setupUi(self)

        # state machine for GUI logic
        self.machine = QtCore.QStateMachine()
        self.states: OrderedDict[str, QtCore.QStateMachine] = OrderedDict({})

        # timers
        self.scale_timer = QtCore.QTimer()
        self.clear_timer = QtCore.QTimer()
        self.clear_timer.setTimerType(QtCore.Qt.TimerType.PreciseTimer)

        # hardware
        self.hw_settings: HardwareSettings = self.parent().model.hardware_settings
        self.bpod = Bpod(self.hw_settings.device_bpod.COM_BPOD, skip_initialization=True, disable_behavior_ports=[0, 1, 2, 3])
        self.valve = Valve(self.hw_settings.device_valve)

        # UI related ...
        self.font_database = QtGui.QFontDatabase
        self.font_database.addApplicationFont(':/fonts/7-Segment')
        self.lineEditGrams.setFont(QtGui.QFont('7-Segment', 30))
        self.action_grams = self.lineEditGrams.addAction(
            QtGui.QIcon(':/images/grams'), QtWidgets.QLineEdit.ActionPosition.TrailingPosition
        )
        self.action_stable = self.lineEditGrams.addAction(
            QtGui.QIcon(':/images/stable'), QtWidgets.QLineEdit.ActionPosition.LeadingPosition
        )
        self.action_grams.setVisible(False)
        self.action_stable.setVisible(False)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.setModal(QtCore.Qt.WindowModality.ApplicationModal)

        # set up plot widget
        self.uiPlot.addLegend()
        self.old_calibration = CalibrationPlot(
            self.uiPlot, f'previous calibration ({self.valve.calibration_date})', 'gray', self.valve.values
        )
        self.new_calibration = CalibrationPlot(self.uiPlot, 'new calibration', 'black')
        self.uiPlot.hideButtons()
        self.uiPlot.setMenuEnabled(False)
        self.uiPlot.setMouseEnabled(x=False, y=False)
        self.uiPlot.setBackground(None)
        self.uiPlot.setLabel('bottom', 'Opening Time [ms]')
        self.uiPlot.setLabel('left', 'Volume [μL]')
        self.uiPlot.getViewBox().setLimits(xMin=0, yMin=0)
        self.uiPlot.getViewBox().enableAutoRange(True)

        # signals & slots
        self.scale_text_changed.connect(self.display_scale_text)
        self.scale_stable_changed.connect(self.display_scale_stable)
        self.pushButtonPulseValve.clicked.connect(self.pulse_valve)
        self.pushButtonToggleValve.clicked.connect(self.toggle_valve)
        self.pushButtonTareScale.clicked.connect(self.tare)
        self.pushButtonSave.setEnabled(False)
        self.pushButtonCancel.clicked.connect(self.close)
        self.pushButtonRestart.setVisible(False)
        self.scale_initialized.connect(self.define_and_start_state_machine)

        # initialize scale
        worker = Worker(self.initialize_scale, port=self.hw_settings.device_scale.COM_SCALE)
        worker.signals.result.connect(self._on_initialize_scale_result)
        QThreadPool.globalInstance().tryStart(worker)

        self.show()

    @QtCore.pyqtSlot(bool)
    def define_and_start_state_machine(self, use_scale: bool = False) -> None:
        for state_name in ['start', 'beaker', 'beaker2', 'flow', 'clear', 'tare', 'calibrate', 'finished', 'save']:
            self.states[state_name] = QtCore.QState(self.machine)
        self.machine.setInitialState(self.states['start'])

        # state 'start': welcome the user and explain what's going on --------------------------------------------------
        self.states['start'].assignProperty(self.labelGuideHead, 'text', 'Welcome')
        self.states['start'].assignProperty(
            self.labelGuideText,
            'text',
            'This is a step-by-step guide for calibrating the valve of your rig. You can abort the process at any time by '
            'pressing Cancel or closing this window.',
        )
        self.states['start'].assignProperty(self.commandLinkNext, 'enabled', True)
        self.states['start'].addTransition(self.commandLinkNext.clicked, self.states['beaker'])

        # state 'beaker': ask user to position beaker on scale ---------------------------------------------------------
        self.states['beaker'].assignProperty(self.labelGuideHead, 'text', 'Preparation')
        self.states['beaker'].assignProperty(
            self.labelGuideText,
            'text',
            'Fill the water reservoir to the level used during experiments.\n\n'
            'Place a small beaker on the scale and position the lick spout directly above.\n\n'
            'The opening of the spout should be placed at a vertical position identical to the one used during '
            'experiments.',
        )
        self.states['beaker'].entered.connect(self.clear_calibration)
        self.states['beaker'].assignProperty(self.pushButtonRestart, 'visible', False)
        self.states['beaker'].assignProperty(self.commandLinkNext, 'visible', True)
        self.states['beaker'].assignProperty(self.commandLinkNext, 'enabled', True)
        self.states['beaker'].assignProperty(self.pushButtonSave, 'enabled', False)
        self.states['beaker'].assignProperty(self.pushButtonTareScale, 'enabled', use_scale)
        self.states['beaker'].assignProperty(self.pushButtonToggleValve, 'enabled', True)
        self.states['beaker'].assignProperty(self.pushButtonPulseValve, 'enabled', True)
        self.states['beaker'].addTransition(self.commandLinkNext.clicked, self.states['beaker2'])

        # state 'beaker': ask user to position beaker on scale ---------------------------------------------------------
        self.states['beaker2'].assignProperty(self.labelGuideHead, 'text', 'Preparation')
        self.states['beaker2'].assignProperty(
            self.labelGuideText,
            'text',
            'Make sure that neither lick spout nor tubing touch the beaker or the scale and that water drops can '
            'freely fall into the beaker.',
        )
        self.states['beaker2'].addTransition(self.commandLinkNext.clicked, self.states['flow'])

        # state 'flow': prepare flow of water --------------------------------------------------------------------------
        self.states['flow'].assignProperty(self.labelGuideHead, 'text', 'Preparation')
        self.states['flow'].assignProperty(
            self.labelGuideText,
            'text',
            'Use the valve controls above to advance the flow of the water until there are no visible pockets of air within the '
            'tubing and first drops start falling into the beaker.',
        )
        self.states['flow'].addTransition(self.commandLinkNext.clicked, self.states['clear'])

        # state 'clear': try to clear one drop of water to set a defined start point for calibration -------------------
        self.states['clear'].entered.connect(self.clear_drop)
        self.states['clear'].assignProperty(self.pushButtonTareScale, 'enabled', False)
        self.states['clear'].assignProperty(self.pushButtonToggleValve, 'enabled', False)
        if use_scale:
            self.states['clear'].assignProperty(self.pushButtonPulseValve, 'enabled', False)
            self.states['clear'].assignProperty(self.commandLinkNext, 'enabled', False)
            self.states['clear'].addTransition(self.drop_cleared, self.states['tare'])
        else:
            self.states['clear'].assignProperty(self.pushButtonPulseValve, 'enabled', True)
            self.states['clear'].assignProperty(self.commandLinkNext, 'enabled', True)
            self.states['clear'].addTransition(self.commandLinkNext.clicked, self.states['tare'])

        # state 'tare': tare the scale ---------------------------------------------------------------------------------
        self.states['tare'].assignProperty(self.pushButtonPulseValve, 'enabled', False)
        if use_scale:
            self.states['tare'].entered.connect(self.tare)
            self.states['tare'].addTransition(self.tared, self.states['calibrate'])
        else:
            self.states['tare'].assignProperty(self.labelGuideText, 'text', 'Tare the scale.')
            self.states['tare'].addTransition(self.commandLinkNext.clicked, self.states['calibrate'])

        # state 'calibrate': perform the actual measurement ------------------------------------------------------------
        self.states['calibrate'].entered.connect(self.calibrate)
        self.states['calibrate'].assignProperty(self.commandLinkNext, 'enabled', False)
        self.states['calibrate'].addTransition(self.start_next_calibration, self.states['clear'])
        self.states['calibrate'].addTransition(self.calibration_finished, self.states['finished'])

        # state 'finished': ask user to save or discard the calibration ------------------------------------------------
        self.states['finished'].assignProperty(self.labelGuideHead, 'text', 'Calibration is finished')
        self.states['finished'].assignProperty(
            self.labelGuideText,
            'text',
            'Click Save to store the calibration. Close this window or click Cancel to discard the calibration.',
        )
        self.states['finished'].assignProperty(self.commandLinkNext, 'visible', False)
        self.states['finished'].assignProperty(self.pushButtonSave, 'enabled', True)
        self.states['finished'].assignProperty(self.pushButtonRestart, 'visible', True)
        self.states['finished'].addTransition(self.pushButtonRestart.clicked, self.states['beaker'])
        self.states['finished'].addTransition(self.pushButtonSave.clicked, self.states['save'])

        # state 'save': save calibration and quit ----------------------------------------------------------------------
        self.states['save'].entered.connect(self.save)
        self.states['save'].assignProperty(self, 'enabled', False)

        self.machine.start()

    def clear_calibration(self):
        self.new_calibration.clear()
        self._next_calibration_time = self.get_next_calibration_time()

    def get_next_calibration_time(self) -> float | None:
        remaining_calibration_times = [
            t for t in self.valve.new_calibration_open_times if t not in self.new_calibration.values.open_times_ms
        ]
        if len(remaining_calibration_times) > 0:
            return max(remaining_calibration_times)
        else:
            return None

    def initialize_scale(self, port: str) -> bool:
        if port is None:
            self.groupBoxScale.setVisible(False)
            return False
        try:
            self.lineEditGrams.setAlignment(QtCore.Qt.AlignCenter)
            self.lineEditGrams.setText('Starting')
            self.scale = Scale(port)
            return True
        except (AssertionError, SerialException):
            log.error(f'Error initializing OHAUS scale on {port}.')
            return False

    def _on_initialize_scale_result(self, success: bool):
        if success:
            self.lineEditGrams.setEnabled(True)
            self.pushButtonTareScale.setEnabled(True)
            self.lineEditGrams.setAlignment(QtCore.Qt.AlignRight)
            self.lineEditGrams.setText('')
            self.scale_timer.timeout.connect(self.get_scale_reading)
            self.action_grams.setVisible(True)
            self.get_scale_reading()
            self.scale_timer.start(self._scale_update_ms)
        else:
            self.lineEditGrams.setAlignment(QtCore.Qt.AlignCenter)
            self.lineEditGrams.setText('Error')
        self.scale_initialized.emit(success)

    def get_scale_reading(self):
        grams, stable = self.scale.get_grams()
        if grams != self._grams:
            self.scale_text_changed.emit(f'{grams:0.2f}')
        if stable != self._stable:
            self.scale_stable_changed.emit(stable)
        self._grams = grams
        self._stable = stable

    @QtCore.pyqtSlot(str)
    def display_scale_text(self, value: str):
        self.lineEditGrams.setText(value)

    @QtCore.pyqtSlot(bool)
    def display_scale_stable(self, value: bool):
        self.action_stable.setVisible(value)

    def toggle_valve(self):
        state = self.pushButtonToggleValve.isChecked()
        self.pushButtonToggleValve.setStyleSheet('QPushButton {background-color: rgb(128, 128, 255);}' if state else '')
        try:
            self.bpod.open_valve(open=state)
        except (OSError, BpodErrorException):
            self.pushButtonToggleValve.setChecked(False)
            self.pushButtonToggleValve.setStyleSheet('')

    def pulse_valve(self):
        self.bpod.pulse_valve(0.05)

    def clear_drop(self):
        self.labelGuideHead.setText('Calibration')
        if self.scale is None:
            self.labelGuideText.setText(
                "Use the 'Pulse Valve' button above to clear one drop of water in order to obtain a defined starting point for "
                'calibration.'
            )
        else:
            self.labelGuideText.setText(
                'Trying to automatically clear one drop of water to obtain a defined starting point for calibration.'
            )
            initial_grams = self.scale.get_stable_grams()
            self._clear_drop_counter = 0
            timer_callback = functools.partial(self.clear_crop_callback, initial_grams)
            self.clear_timer.timeout.connect(timer_callback)
            self.clear_timer.start(500)

    def clear_crop_callback(self, initial_grams: float, duration_s: float = 0.05):
        if self.scale.get_grams()[0] > initial_grams + 0.02:
            self.clear_timer.stop()
            self.drop_cleared.emit(self._clear_drop_counter)
            return
        self._clear_drop_counter += 1
        self.bpod.pulse_valve(duration_s)

    def tare(self):
        self.scale_timer.stop()
        self.scale_text_changed.emit('------')
        self._grams = float('nan')
        worker = Worker(self.scale.tare)
        worker.signals.result.connect(self._on_tare_finished)
        QThreadPool.globalInstance().tryStart(worker)

    @QtCore.pyqtSlot(object)
    def _on_tare_finished(self, success: bool):
        self.scale_timer.start(self._scale_update_ms)
        self.tared.emit(success)

    @QtCore.pyqtSlot()
    def calibrate(self):
        n_samples = int(np.ceil(50 * max(self.valve.new_calibration_open_times) / self._next_calibration_time))
        self.labelGuideText.setText(
            f'Getting {n_samples} samples for a valve opening time of {self._next_calibration_time} ms ...'
        )
        worker = Worker(self.bpod.pulse_valve_repeatedly, n_samples, self._next_calibration_time / 1e3, 0.2)
        worker.signals.result.connect(self._on_repeated_pulse_finished)
        QThreadPool.globalInstance().tryStart(worker)

    @QtCore.pyqtSlot(object)
    def _on_repeated_pulse_finished(self, n_pulses: int):
        if self.scale is None:
            ok = False
            scale_reading = 0
            while not ok or scale_reading <= 0:
                scale_reading, ok = QtWidgets.QInputDialog().getDouble(
                    self,
                    'Enter Scale Reading',
                    'Enter measured weight in grams:',
                    min=0,
                    max=float('inf'),
                    decimals=2,
                    flags=(QtWidgets.QInputDialog().windowFlags() & ~QtCore.Qt.WindowType.WindowContextHelpButtonHint),
                )
            grams_per_pulse = scale_reading / n_pulses
        else:
            scale_reading = self.scale.get_stable_grams()
            grams_per_pulse = scale_reading / n_pulses
        self.new_calibration.values.add_samples([self._next_calibration_time], [grams_per_pulse])
        self.new_calibration.update()
        self._next_calibration_time = self.get_next_calibration_time()
        if self._next_calibration_time is None:
            self.calibration_finished.emit()
        else:
            self.start_next_calibration.emit()

    def save(self) -> None:
        valve_settings = self.hw_settings.device_valve
        valve_settings.WATER_CALIBRATION_OPEN_TIMES = [float(x) for x in self.new_calibration.values.open_times_ms]
        valve_settings.WATER_CALIBRATION_WEIGHT_PERDROP = [float(x) for x in self.new_calibration.values.volumes_ul]
        valve_settings.WATER_CALIBRATION_DATE = date.today()
        self.parent().model.hardware_settings.device_valve = valve_settings
        save_pydantic_yaml(self.parent().model.hardware_settings)
        self.labelGuideHead.setText('Settings saved.')
        self.labelGuideText.setText('')
        QtCore.QTimer.singleShot(1000, self.close)

    @override
    def closeEvent(self, event):
        self.clear_timer.stop()
        self.scale_timer.stop()
        if self.machine.started:
            self.machine.stop()
        if self.bpod.is_connected:
            self.bpod.stop_trial()
        self.deleteLater()
