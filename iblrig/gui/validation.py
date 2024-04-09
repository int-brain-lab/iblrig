from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import QMutex, QThreadPool
from PyQt5.QtGui import QFont, QIcon, QStandardItem, QStandardItemModel
from PyQt5.QtWidgets import QHeaderView

from iblrig.gui.tools import Worker
from iblrig.gui.ui_validation import Ui_validation
from iblrig.hardware_validation import Result, Status, Validator, get_all_validators
from iblrig.pydantic_definitions import HardwareSettings, RigSettings

SECTION_FONT = QFont(None, -1, QFont.Bold, False)
STATUS_ICON: dict[Status, QIcon()] = {
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
    status: Status

    def __init__(self, validator: type[Validator], hardware_settings: HardwareSettings, rig_settings: RigSettings):
        super().__init__()
        self.validator = validator(hardware_settings=hardware_settings, iblrig_settings=rig_settings, interactive=True)
        self.setIcon(QIcon(STATUS_ICON[Status.PEND]))
        self.setText(self.validator.name)
        self.setFont(SECTION_FONT)
        self.mutex = QMutex()

    def run(self) -> Status:
        self.clear()
        results: list[Result] = []
        for result in self.validator.run():
            results.append(result)
            result_item = QStandardItem(result.message)
            result_item.setToolTip(result.message)
            result_item.setIcon(STATUS_ICON[result.status])
            self.appendRow([result_item, QStandardItem('')])
            if result.solution is not None and len(result.solution) > 0:
                solution_item = QStandardItem(f'Suggestion: {result.solution}')
                solution_item.setIcon(QIcon(':/images/validation_suggestion'))
                self.appendRow(solution_item)

        # determine return value
        statuses = [r.status for r in results]
        if Status.SKIP in statuses:
            return_status = Status.SKIP
        elif Status.FAIL in statuses:
            return_status = Status.FAIL
        elif Status.WARN in statuses:
            return_status = Status.WARN
        else:
            return_status = Status.PASS

        self.setIcon(STATUS_ICON[return_status])
        return return_status

    def clear(self):
        self.setIcon(QIcon(STATUS_ICON[Status.PEND]))
        while self.hasChildren():
            self.removeRow(0)


class SystemValidationDialog(QtWidgets.QDialog, Ui_validation):
    validator_items: list[ValidatorItem] = []
    status_items: list[StatusItem] = []

    def __init__(self, *args, hardware_settings: HardwareSettings, rig_settings: RigSettings, **kwargs) -> None:
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

        self.show()
        self.run()

    def run(self):
        QThreadPool.globalInstance().tryStart(self.worker)

    def run_subprocess(self):
        self.pushButtonOK.setEnabled(False)
        self.pushButtonRerun.setEnabled(False)
        self.treeView.expandAll()

        for idx, validator_item in enumerate(self.validator_items):
            validator_item.clear()
            self.status_items[idx].status = Status.PEND
            self.treeView.scrollToTop()
        for idx, validator_item in enumerate(self.validator_items):
            self.status_items[idx].setText('running')
            status = validator_item.run()
            self.status_items[idx].status = status
            if status == Status.PASS:
                self.treeView.collapse(validator_item.index())
            self.treeView.scrollToBottom()
