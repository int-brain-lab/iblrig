import functools
import logging
from collections import OrderedDict

import numpy as np
import pyqtgraph as pg
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QThreadPool
from pyqtgraph import PlotWidget
from serial import SerialException

from iblrig.gui.tools import Worker
from iblrig.gui.ui_valve import Ui_valve
from iblrig.hardware import Bpod
from iblrig.pydantic_definitions import HardwareSettings
from iblrig.scale import Scale
from iblrig.valve import Valve, ValveValues
from pybpodapi.exceptions.bpod_error import BpodErrorException

log = logging.getLogger(__name__)


class CalibrationPlot:
    def __init__(self, parent: PlotWidget, name: str, color: str, values: ValveValues | None = None):
        self._values = values if values is not None else ValveValues([], [])
        self._curve = pg.PlotCurveItem(name=name)
        self._curve.setPen(color=color, width=3)
        self._points = pg.ScatterPlotItem(name=name)
        self._points.setPen(color=color)
        self._points.setBrush(color=color)
        parent.addItem(self._curve)
        parent.addItem(self._points)
        self._update()

    @property
    def values(self) -> ValveValues:
        return self._values

    @values.setter
    def values(self, values: ValveValues):
        self._values = values
        self._update()

    def _update(self):
        if len(self.values.open_times_ms) == 0:
            return
        time_range = list(np.linspace(self.values.open_times_ms[0], self.values.open_times_ms[-1], 100))
        self._curve.setData(x=time_range, y=self.values.ms2ul(time_range))
        self._points.setData(x=self.values.open_times_ms, y=self.values.volumes_ul)


class ValveCalibrationDialog(QtWidgets.QDialog, Ui_valve):
    scale: Scale | None = None
    scale_text_changed = QtCore.pyqtSignal(str)
    scale_stable_changed = QtCore.pyqtSignal(bool)
    drop_cleared = QtCore.pyqtSignal()
    _grams = float('nan')
    _stable = False
    _next_calibration_step = 1
    _scale_update_ms = 100

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setupUi(self)

        # hardware
        hw_settings: HardwareSettings = self.parent().model.hardware_settings
        self.bpod = Bpod(hw_settings.device_bpod.COM_BPOD, skip_initialization=True, disable_behavior_ports=[0, 1, 2, 3])
        self.valve = Valve(hw_settings.device_valve)

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

        # set up scale reading
        self.scale_timer = QtCore.QTimer()
        if hw_settings.device_scale.COM_SCALE is not None:
            worker = Worker(self.initialize_scale, port=hw_settings.device_scale.COM_SCALE)
            worker.signals.result.connect(self._on_initialize_scale_result)
            QThreadPool.globalInstance().tryStart(worker)
        else:
            self.lineEditGrams.setAlignment(QtCore.Qt.AlignCenter)
            self.lineEditGrams.setText('no Scale')

        # set up plot widget
        self.old_calibration = CalibrationPlot(self.uiPlot, 'previous calibration', 'gray', self.valve.values)
        self.new_calibration = CalibrationPlot(self.uiPlot, 'new calibration', 'gray')
        self.uiPlot.hideButtons()
        self.uiPlot.setMenuEnabled(False)
        self.uiPlot.setMouseEnabled(x=False, y=False)
        self.uiPlot.setBackground(None)
        self.uiPlot.setLabel('bottom', 'Opening Time [ms]')
        self.uiPlot.setLabel('left', 'Volume [μL]')
        self.uiPlot.getViewBox().setLimits(xMin=0, yMin=0)

        # signals & slots
        self.scale_text_changed.connect(self.display_scale_text)
        self.scale_stable_changed.connect(self.display_scale_stable)
        self.pushButtonPulseValve.clicked.connect(self.pulse_valve)
        self.pushButtonToggleValve.clicked.connect(self.toggle_valve)
        self.pushButtonTareScale.clicked.connect(self.tare)
        self.pushButtonSave.setEnabled(False)
        self.pushButtonCancel.clicked.connect(self.close)
        self.pushButtonRestart.setVisible(False)

        # Definition of state machine for guided calibration ===========================================================
        self.machine = QtCore.QStateMachine()
        self.states: OrderedDict[str, QtCore.QState] = OrderedDict()

        state = self._add_guide_state(
            name='start',
            head='Welcome',
            text='This is a step-by-step guide for calibrating the valve of your rig. You can abort the process at any '
                 'time by pressing Cancel or closing this window.',
        )

        state = self._add_guide_state(
            name='preparation_beaker',
            head='Preparation',
            text='Place a small beaker on the scale and position the lick spout directly above it.\n\nMake sure that '
                 'neither the lick spout itself nor the tubing touch the beaker or the scale and that the water drops '
                 'can freely fall into the beaker.',
        )

        state = self._add_guide_state(
            name='preparation_flow',
            head='Preparation',
            text='Use the valve controls above to advance the flow of the water until there are no visible pockets of '
                 'air within the tubing and first drops start falling into the beaker.',
        )
        state.assignProperty(self.commandLinkNext, 'visible', True)
        state.assignProperty(self.pushButtonRestart, 'visible', False)
        state.assignProperty(self.pushButtonSave, 'enabled', False)

        state = self._add_guide_state(name='calibration_clear', text='hello')
        state.entered.connect(self.clear_drop)
        state.assignProperty(self.commandLinkNext, 'enabled', False)

        state = self._add_guide_state(name='calibration_tare', transition_signal=self.drop_cleared)
        state.entered.connect(self.tare)

        state = self._add_guide_state(name='calibration_finished', transition_signal=self.states[
            'calibration_tare'].finished)
        state.assignProperty(self.commandLinkNext, 'enabled', True)

        # # Sub-State 3.1 --- Clear Drop
        # sub_states = [sub_state := QtCore.QState(state)]
        # sub_state.assignProperty(self.commandLinkNext, 'enabled', False)
        # sub_state.entered.connect(self.clear_drop)
        #
        # # Sub-State 3.2 --- Final Sub-State
        # sub_states.append(sub_state := QtCore.QState(state))
        # sub_state.addTransition(self.drop_cleared, sub_state)
        # sub_state.assignProperty(self.commandLinkNext, 'enabled', True)
        # sub_state.addTransition(sub_state.finished, QtCore.QFinalState())
        #
        # state.setInitialState(sub_state[0])

        # State 4: Finish
        state = self._add_guide_state(
            name='finished',
            head='Calibration is finished',
            text='Click Save to store the calibration. Close this window or click Cancel to discard the calibration.',
        )
        state.assignProperty(self.commandLinkNext, 'visible', False)
        state.assignProperty(self.pushButtonSave, 'enabled', True)
        state.assignProperty(self.pushButtonRestart, 'visible', True)
        state.addTransition(self.pushButtonRestart.clicked, self.states['preparation_flow'])

        # Step 5: Save and exit
        state = self._add_guide_state(name='save', transition_signal=self.pushButtonSave.clicked)
        state.addTransition(self.states['save'].finished, QtCore.QFinalState())

        self.machine.setInitialState(self.states['start'])
        self.machine.start()
        self.show()

    def _add_guide_state(
            self,
            name: str,
            head: str | None = None,
            text: str | None = None,
            transition_from_previous: bool = True,
            transition_signal: QtCore.pyqtSignal | None = None,
    ) -> QtCore.QState:
        assert name not in self.states.keys(), 'name of state needs to be unique'

        this_state = QtCore.QState()

        if head is not None:
            this_state.assignProperty(self.labelGuideHead, 'text', head)
        if text is not None:
            this_state.assignProperty(self.labelGuideText, 'text', text)

        if transition_from_previous and len(self.states) > 0:
            prev_state = list(self.states.values())[-1]
            signal = self.commandLinkNext.clicked if transition_signal is None else transition_signal
            prev_state.addTransition(signal, this_state)

        self.states[name] = this_state
        self.machine.addState(this_state)
        return this_state

    def initialize_scale(self, port: str) -> bool:
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

    # def guided_calibration(self):
    #     guide_string = self._guide_strings.get(self._next_calibration_step, '')
    #     self.labelGuideText.setText(guide_string)
    #     match self._next_calibration_step:
    #         case 3:
    #             self.clear_drop()
    #         case 4:
    #             self.tare()
    #             worker = Worker(self.bpod.pulse_valve_repeatedly, repetitions=100, open_time_s=0.05, close_time_s=0.05)
    #             QThreadPool.globalInstance().tryStart(worker)
    #             # worker.signals.result.connect(self._on_initialize_scale_result)
    #             # self.bpod.pulse_valve_repeatedly(100, 0.05)
    #     self._next_calibration_step += 1

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
        if self.scale is None:
            pass
        else:
            initial_grams = self.scale.get_stable_grams()
            timer = QtCore.QTimer()
            timer.setTimerType(QtCore.Qt.TimerType.PreciseTimer)
            timer_callback = functools.partial(self.clear_crop_callback, initial_grams, timer)
            timer.timeout.connect(timer_callback)
            timer.start(500)

    def clear_crop_callback(self, initial_grams: float, timer: QtCore.QTimer):
        if self.scale.get_grams()[0] > initial_grams + 0.02:
            timer.stop()
            self.drop_cleared.emit()
            return
        self.pulse_valve()

    def tare(self):
        if self.scale is None:
            return
        self.scale_timer.stop()
        self.scale_text_changed.emit('------')
        self._grams = float('nan')
        worker = Worker(self.scale.tare)
        worker.signals.result.connect(self._on_tare_finished)
        QThreadPool.globalInstance().tryStart(worker)

    @QtCore.pyqtSlot(object)
    def _on_tare_finished(self, value: bool):
        QtCore.QTimer.singleShot(200, lambda: self.scale_timer.start(self._scale_update_ms))

    def closeEvent(self, event) -> bool:
        if self.scale is not None:
            self.scale_timer.stop()
        if self.machine.started:
            self.machine.stop()
