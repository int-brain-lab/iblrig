from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import QThreadPool, pyqtSlot
from PyQt5.QtGui import QFont, QIcon, QStandardItem, QStandardItemModel
from PyQt5.QtWidgets import QHeaderView

from iblrig.gui.tools import Worker
from iblrig.gui.ui_validation import Ui_validation
from iblrig.hardware_validation import Result, Status, Validator, get_all_validators
from iblrig.pydantic_definitions import HardwareSettings, RigSettings

SECTION_FONT = QFont('', -1, QFont.Bold, False)
STATUS_ICON: dict[Status, QIcon] = {
    Status.PASS: QIcon(':/images/validation_pass'),
    Status.WARN: QIcon(':/images/validation_warn'),
    Status.FAIL: QIcon(':/images/validation_fail'),
    Status.INFO: QIcon(':/images/validation_info'),
    Status.SKIP: QIcon(':/images/validation_skip'),
    Status.PEND: QIcon(':/images/validation_pending'),
}


class StatusItem(QStandardItem):
    _status: Status

    def __init__(self, status: Status):
        super().__init__()
        self.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.status = status

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, status: Status):
        self._status = status
        match status:
            case Status.PEND:
                self.setText('pending')
            case Status.PASS:
                self.setText('passed')
            case Status.WARN:
                self.setText('warning')
            case Status.FAIL:
                self.setText('failed')
            case Status.INFO:
                self.setText('')
            case Status.SKIP:
                self.setText('skipped')


class ValidatorItem(QStandardItem):
    validator: Validator
    _status: Status

    def __init__(self, validator: type[Validator], hardware_settings: HardwareSettings, rig_settings: RigSettings):
        super().__init__()
        self.status = Status.PEND
        self.validator = validator(hardware_settings=hardware_settings, iblrig_settings=rig_settings, interactive=True)
        self.setText(self.validator.name)
        self.setFont(SECTION_FONT)

    @property
    def status(self) -> Status:
        return self._status

    @status.setter
    def status(self, status: Status):
        self._status = status
        self.setIcon(QIcon(STATUS_ICON[status]))

    def clear(self):
        self.status = Status.PEND
        while self.hasChildren():
            self.removeRow(0)


class SystemValidationDialog(QtWidgets.QDialog, Ui_validation):
    validator_items: list[ValidatorItem] = []
    status_items: list[StatusItem] = []
    item_started = QtCore.pyqtSignal(int)
    item_result = QtCore.pyqtSignal(int, Result)
    item_finished = QtCore.pyqtSignal(int, Status)

    def __init__(self, *args, hardware_settings: HardwareSettings, rig_settings: RigSettings, **kwargs) -> None:
        """
        Dialog for system validation.

        Parameters
        ----------
        *args
            Arguments to pass to the QDialog constructor.
        hardware_settings : HardwareSettings
            Pydantic model with data parsed from hardware_settings.yaml
        rig_settings : RigSettings
            Pydantic model with data parsed from iblrig_settings.yaml
        **kwargs
            Keyword arguments to pass to the QDialog constructor.

        """
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowType.WindowContextHelpButtonHint)

        self.worker = Worker(self.run_subprocess)
        self.worker.setAutoDelete(False)
        self.worker.signals.finished.connect(lambda: self.pushButtonRerun.setEnabled(True))
        self.worker.signals.finished.connect(lambda: self.pushButtonOK.setEnabled(True))

        self.treeModel = QStandardItemModel()
        self.treeModel.setColumnCount(2)

        for validator in get_all_validators():
            self.validator_items.append(ValidatorItem(validator, hardware_settings, rig_settings))
            self.status_items.append(StatusItem(Status.PEND))
            self.status_items[-1].setFont(SECTION_FONT)
            self.treeModel.appendRow([self.validator_items[-1], self.status_items[-1]])

        self.treeView.setModel(self.treeModel)
        self.treeView.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.treeView.header().setSectionResizeMode(1, QHeaderView.Fixed)
        self.treeView.header().resizeSection(1, 60)

        self.pushButtonOK.clicked.connect(self.close)
        self.pushButtonRerun.clicked.connect(self.run)
        self.item_started.connect(self.on_item_started)
        self.item_result.connect(self.on_item_result)
        self.item_finished.connect(self.on_item_finished)

        self.show()
        self.run()

    def run(self):
        """Prepare GUI and start worker thread for running validators."""
        self.pushButtonOK.setEnabled(False)
        self.pushButtonRerun.setEnabled(False)
        self.treeView.expandAll()
        for idx, _ in enumerate(self.validator_items):
            self.validator_items[idx].clear()
            self.status_items[idx].status = Status.PEND
            self.treeView.scrollToTop()
        self.update()
        QThreadPool.globalInstance().tryStart(self.worker)

    def run_subprocess(self):
        """Run all validators in a subprocess."""
        for idx, validator_item in enumerate(self.validator_items):
            self.item_started.emit(idx)
            results = []
            for result in validator_item.validator.run():
                results.append(result)
                self.item_result.emit(idx, result)

            statuses = [r.status for r in results]
            if Status.SKIP in statuses:
                status = Status.SKIP
            elif Status.FAIL in statuses:
                status = Status.FAIL
            elif Status.WARN in statuses:
                status = Status.WARN
            else:
                status = Status.PASS
            self.item_finished.emit(idx, status)

    @pyqtSlot(int)
    def on_item_started(self, idx: int):
        self.status_items[idx].setText('running')

    @pyqtSlot(int, Result)
    def on_item_result(self, idx: int, result: Result):
        result_item = QStandardItem(result.message)
        result_item.setToolTip(result.message)
        result_item.setIcon(STATUS_ICON[result.status])
        self.validator_items[idx].appendRow([result_item, QStandardItem('')])
        if result.solution is not None and len(result.solution) > 0:
            solution_item = QStandardItem(f'Suggestion: {result.solution}')
            solution_item.setIcon(QIcon(':/images/validation_suggestion'))
            self.validator_items[idx].appendRow(solution_item)
        self.update()

    @pyqtSlot(int, Status)
    def on_item_finished(self, idx: int, status: Status):
        self.validator_items[idx].status = status
        self.status_items[idx].status = status
        if status == Status.PASS:
            self.treeView.collapse(self.validator_items[idx].index())
        self.treeView.scrollToBottom()
        self.update()
