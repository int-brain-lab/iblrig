# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'iblrig/gui/ui_wizard.ui'
#
# Created by: PyQt5 UI code generator 5.15.9
#
# WARNING: Any manual changes made to this file will be lost when pyuic5 is
# run again.  Do not edit this file unless you know what you are doing.


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_wizard(object):
    def setupUi(self, wizard):
        wizard.setObjectName("wizard")
        wizard.resize(450, 633)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.MinimumExpanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(wizard.sizePolicy().hasHeightForWidth())
        wizard.setSizePolicy(sizePolicy)
        wizard.setMinimumSize(QtCore.QSize(450, 0))
        wizard.setMaximumSize(QtCore.QSize(600, 800))
        wizard.setSizeIncrement(QtCore.QSize(0, 0))
        wizard.setContextMenuPolicy(QtCore.Qt.DefaultContextMenu)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(":/images/iblrig_logo"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        wizard.setWindowIcon(icon)
        wizard.setWindowOpacity(1.0)
        wizard.setAutoFillBackground(False)
        wizard.setAnimated(False)
        wizard.setDocumentMode(False)
        self.widget = QtWidgets.QWidget(wizard)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.widget.sizePolicy().hasHeightForWidth())
        self.widget.setSizePolicy(sizePolicy)
        self.widget.setObjectName("widget")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout(self.widget)
        self.horizontalLayout_2.setContentsMargins(6, 6, 6, 0)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.tabWidget = QtWidgets.QTabWidget(self.widget)
        self.tabWidget.setObjectName("tabWidget")
        self.tabSession = QtWidgets.QWidget()
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.tabSession.sizePolicy().hasHeightForWidth())
        self.tabSession.setSizePolicy(sizePolicy)
        self.tabSession.setObjectName("tabSession")
        self.verticalLayoutSession = QtWidgets.QVBoxLayout(self.tabSession)
        self.verticalLayoutSession.setObjectName("verticalLayoutSession")
        self.uiGroupParameters = QtWidgets.QWidget(self.tabSession)
        self.uiGroupParameters.setObjectName("uiGroupParameters")
        self.formLayout = QtWidgets.QFormLayout(self.uiGroupParameters)
        self.formLayout.setSizeConstraint(QtWidgets.QLayout.SetDefaultConstraint)
        self.formLayout.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)
        self.formLayout.setLabelAlignment(QtCore.Qt.AlignRight|QtCore.Qt.AlignTrailing|QtCore.Qt.AlignVCenter)
        self.formLayout.setContentsMargins(0, 0, 0, 0)
        self.formLayout.setObjectName("formLayout")
        self.labelUser = QtWidgets.QLabel(self.uiGroupParameters)
        self.labelUser.setObjectName("labelUser")
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.LabelRole, self.labelUser)
        self.widget_2 = QtWidgets.QWidget(self.uiGroupParameters)
        self.widget_2.setObjectName("widget_2")
        self.horizontalLayout_4 = QtWidgets.QHBoxLayout(self.widget_2)
        self.horizontalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")
        self.uiLineEditUser = LineEditAlyxUser(self.widget_2)
        self.uiLineEditUser.setObjectName("uiLineEditUser")
        self.horizontalLayout_4.addWidget(self.uiLineEditUser)
        self.uiPushButtonLogIn = QtWidgets.QPushButton(self.widget_2)
        self.uiPushButtonLogIn.setMinimumSize(QtCore.QSize(100, 0))
        self.uiPushButtonLogIn.setObjectName("uiPushButtonLogIn")
        self.horizontalLayout_4.addWidget(self.uiPushButtonLogIn)
        self.horizontalLayout_4.setStretch(0, 2)
        self.horizontalLayout_4.setStretch(1, 1)
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.FieldRole, self.widget_2)
        self.labelSubject = QtWidgets.QLabel(self.uiGroupParameters)
        self.labelSubject.setObjectName("labelSubject")
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.LabelRole, self.labelSubject)
        self.widget_4 = QtWidgets.QWidget(self.uiGroupParameters)
        self.widget_4.setObjectName("widget_4")
        self.horizontalLayout = QtWidgets.QHBoxLayout(self.widget_4)
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.uiComboSubject = QtWidgets.QComboBox(self.widget_4)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.uiComboSubject.sizePolicy().hasHeightForWidth())
        self.uiComboSubject.setSizePolicy(sizePolicy)
        self.uiComboSubject.setObjectName("uiComboSubject")
        self.horizontalLayout.addWidget(self.uiComboSubject)
        self.lineEditSubject = QtWidgets.QLineEdit(self.widget_4)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.lineEditSubject.sizePolicy().hasHeightForWidth())
        self.lineEditSubject.setSizePolicy(sizePolicy)
        self.lineEditSubject.setMinimumSize(QtCore.QSize(100, 0))
        self.lineEditSubject.setMaximumSize(QtCore.QSize(200, 16777215))
        self.lineEditSubject.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.lineEditSubject.setObjectName("lineEditSubject")
        self.horizontalLayout.addWidget(self.lineEditSubject)
        self.horizontalLayout.setStretch(0, 2)
        self.horizontalLayout.setStretch(1, 1)
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.FieldRole, self.widget_4)
        self.labelProject = QtWidgets.QLabel(self.uiGroupParameters)
        self.labelProject.setObjectName("labelProject")
        self.formLayout.setWidget(2, QtWidgets.QFormLayout.LabelRole, self.labelProject)
        self.uiListProjects = QtWidgets.QListView(self.uiGroupParameters)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.uiListProjects.sizePolicy().hasHeightForWidth())
        self.uiListProjects.setSizePolicy(sizePolicy)
        self.uiListProjects.setMinimumSize(QtCore.QSize(0, 80))
        self.uiListProjects.setMaximumSize(QtCore.QSize(16777215, 80))
        palette = QtGui.QPalette()
        brush = QtGui.QBrush(QtGui.QColor(0, 120, 215))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Highlight, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.HighlightedText, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 120, 215))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Highlight, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.HighlightedText, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 120, 215))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Highlight, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.HighlightedText, brush)
        self.uiListProjects.setPalette(palette)
        self.uiListProjects.viewport().setProperty("cursor", QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.uiListProjects.setFocusPolicy(QtCore.Qt.TabFocus)
        self.uiListProjects.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.uiListProjects.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.uiListProjects.setObjectName("uiListProjects")
        self.formLayout.setWidget(2, QtWidgets.QFormLayout.FieldRole, self.uiListProjects)
        self.labelProcedure = QtWidgets.QLabel(self.uiGroupParameters)
        self.labelProcedure.setObjectName("labelProcedure")
        self.formLayout.setWidget(3, QtWidgets.QFormLayout.LabelRole, self.labelProcedure)
        self.uiListProcedures = QtWidgets.QListView(self.uiGroupParameters)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.uiListProcedures.sizePolicy().hasHeightForWidth())
        self.uiListProcedures.setSizePolicy(sizePolicy)
        self.uiListProcedures.setMinimumSize(QtCore.QSize(0, 80))
        self.uiListProcedures.setMaximumSize(QtCore.QSize(16777215, 80))
        palette = QtGui.QPalette()
        brush = QtGui.QBrush(QtGui.QColor(0, 120, 215))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.Highlight, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.HighlightedText, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 120, 215))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.Highlight, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.HighlightedText, brush)
        brush = QtGui.QBrush(QtGui.QColor(0, 120, 215))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.Highlight, brush)
        brush = QtGui.QBrush(QtGui.QColor(255, 255, 255))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.HighlightedText, brush)
        self.uiListProcedures.setPalette(palette)
        self.uiListProcedures.viewport().setProperty("cursor", QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.uiListProcedures.setFocusPolicy(QtCore.Qt.TabFocus)
        self.uiListProcedures.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.uiListProcedures.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        self.uiListProcedures.setObjectName("uiListProcedures")
        self.formLayout.setWidget(3, QtWidgets.QFormLayout.FieldRole, self.uiListProcedures)
        self.labelTask = QtWidgets.QLabel(self.uiGroupParameters)
        self.labelTask.setObjectName("labelTask")
        self.formLayout.setWidget(4, QtWidgets.QFormLayout.LabelRole, self.labelTask)
        self.uiComboTask = QtWidgets.QComboBox(self.uiGroupParameters)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.uiComboTask.sizePolicy().hasHeightForWidth())
        self.uiComboTask.setSizePolicy(sizePolicy)
        self.uiComboTask.setMinimumSize(QtCore.QSize(0, 0))
        self.uiComboTask.setObjectName("uiComboTask")
        self.formLayout.setWidget(4, QtWidgets.QFormLayout.FieldRole, self.uiComboTask)
        self.labelSettings = QtWidgets.QLabel(self.uiGroupParameters)
        self.labelSettings.setObjectName("labelSettings")
        self.formLayout.setWidget(5, QtWidgets.QFormLayout.LabelRole, self.labelSettings)
        self.scrollArea = QtWidgets.QScrollArea(self.uiGroupParameters)
        self.scrollArea.setMinimumSize(QtCore.QSize(0, 110))
        self.scrollArea.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setObjectName("scrollArea")
        self.uiGroupTaskParameters = QtWidgets.QWidget()
        self.uiGroupTaskParameters.setGeometry(QtCore.QRect(0, 0, 339, 110))
        self.uiGroupTaskParameters.setObjectName("uiGroupTaskParameters")
        self.formLayout_2 = QtWidgets.QFormLayout(self.uiGroupTaskParameters)
        self.formLayout_2.setObjectName("formLayout_2")
        self.scrollArea.setWidget(self.uiGroupTaskParameters)
        self.formLayout.setWidget(5, QtWidgets.QFormLayout.FieldRole, self.scrollArea)
        self.verticalLayoutSession.addWidget(self.uiGroupParameters)
        self.widget_3 = QtWidgets.QWidget(self.tabSession)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.widget_3.sizePolicy().hasHeightForWidth())
        self.widget_3.setSizePolicy(sizePolicy)
        self.widget_3.setObjectName("widget_3")
        self.horizontalLayout_8 = QtWidgets.QHBoxLayout(self.widget_3)
        self.horizontalLayout_8.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_8.setObjectName("horizontalLayout_8")
        self.uiGroupTools = QtWidgets.QGroupBox(self.widget_3)
        self.uiGroupTools.setObjectName("uiGroupTools")
        self.verticalLayout_4 = QtWidgets.QVBoxLayout(self.uiGroupTools)
        self.verticalLayout_4.setObjectName("verticalLayout_4")
        self.uiPushFlush = QtWidgets.QPushButton(self.uiGroupTools)
        self.uiPushFlush.setEnabled(True)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.uiPushFlush.sizePolicy().hasHeightForWidth())
        self.uiPushFlush.setSizePolicy(sizePolicy)
        icon1 = QtGui.QIcon()
        icon1.addPixmap(QtGui.QPixmap(":/images/flush"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.uiPushFlush.setIcon(icon1)
        self.uiPushFlush.setCheckable(True)
        self.uiPushFlush.setObjectName("uiPushFlush")
        self.verticalLayout_4.addWidget(self.uiPushFlush)
        self.uiPushReward = QtWidgets.QPushButton(self.uiGroupTools)
        icon2 = QtGui.QIcon()
        icon2.addPixmap(QtGui.QPixmap(":/images/present"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.uiPushReward.setIcon(icon2)
        self.uiPushReward.setObjectName("uiPushReward")
        self.verticalLayout_4.addWidget(self.uiPushReward)
        self.uiPushStatusLED = QtWidgets.QPushButton(self.uiGroupTools)
        icon3 = QtGui.QIcon()
        icon3.addPixmap(QtGui.QPixmap(":/images/status_led"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.uiPushStatusLED.setIcon(icon3)
        self.uiPushStatusLED.setCheckable(True)
        self.uiPushStatusLED.setObjectName("uiPushStatusLED")
        self.verticalLayout_4.addWidget(self.uiPushStatusLED)
        self.horizontalLayout_8.addWidget(self.uiGroupTools)
        self.uiGroupSessionControl = QtWidgets.QGroupBox(self.widget_3)
        self.uiGroupSessionControl.setObjectName("uiGroupSessionControl")
        self.gridLayout_2 = QtWidgets.QGridLayout(self.uiGroupSessionControl)
        self.gridLayout_2.setObjectName("gridLayout_2")
        self.uiCheckAppend = QtWidgets.QCheckBox(self.uiGroupSessionControl)
        self.uiCheckAppend.setObjectName("uiCheckAppend")
        self.gridLayout_2.addWidget(self.uiCheckAppend, 3, 2, 1, 1)
        self.uiPushStart = QtWidgets.QPushButton(self.uiGroupSessionControl)
        self.uiPushStart.setStyleSheet("QPushButton { background-color: red; }")
        self.uiPushStart.setObjectName("uiPushStart")
        self.gridLayout_2.addWidget(self.uiPushStart, 2, 2, 1, 1)
        self.uiPushPause = QtWidgets.QPushButton(self.uiGroupSessionControl)
        self.uiPushPause.setEnabled(False)
        self.uiPushPause.setCheckable(True)
        self.uiPushPause.setChecked(False)
        self.uiPushPause.setObjectName("uiPushPause")
        self.gridLayout_2.addWidget(self.uiPushPause, 2, 1, 1, 1)
        self.horizontalLayout_8.addWidget(self.uiGroupSessionControl)
        self.horizontalLayout_8.setStretch(0, 3)
        self.horizontalLayout_8.setStretch(1, 5)
        self.verticalLayoutSession.addWidget(self.widget_3)
        icon4 = QtGui.QIcon()
        icon4.addPixmap(QtGui.QPixmap(":/images/wheel"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.tabWidget.addTab(self.tabSession, icon4, "")
        self.horizontalLayout_2.addWidget(self.tabWidget)
        wizard.setCentralWidget(self.widget)
        self.statusbar = QtWidgets.QStatusBar(wizard)
        self.statusbar.setEnabled(True)
        self.statusbar.setToolTip("")
        self.statusbar.setSizeGripEnabled(False)
        self.statusbar.setObjectName("statusbar")
        wizard.setStatusBar(self.statusbar)
        self.uiMenuBar = QtWidgets.QMenuBar(wizard)
        self.uiMenuBar.setGeometry(QtCore.QRect(0, 0, 450, 24))
        self.uiMenuBar.setObjectName("uiMenuBar")
        self.uiMenuTools = QtWidgets.QMenu(self.uiMenuBar)
        self.uiMenuTools.setObjectName("uiMenuTools")
        wizard.setMenuBar(self.uiMenuBar)
        self.uiActionTrainingLevelV7 = QtWidgets.QAction(wizard)
        self.uiActionTrainingLevelV7.setObjectName("uiActionTrainingLevelV7")
        self.uiActionCalibrateFrame2ttl = QtWidgets.QAction(wizard)
        self.uiActionCalibrateFrame2ttl.setObjectName("uiActionCalibrateFrame2ttl")
        self.uiActionCalibrateValve = QtWidgets.QAction(wizard)
        self.uiActionCalibrateValve.setObjectName("uiActionCalibrateValve")
        self.uiActionValidateHardware = QtWidgets.QAction(wizard)
        self.uiActionValidateHardware.setObjectName("uiActionValidateHardware")
        self.uiMenuTools.addAction(self.uiActionValidateHardware)
        self.uiMenuTools.addAction(self.uiActionCalibrateFrame2ttl)
        self.uiMenuTools.addAction(self.uiActionCalibrateValve)
        self.uiMenuTools.addAction(self.uiActionTrainingLevelV7)
        self.uiMenuBar.addAction(self.uiMenuTools.menuAction())
        self.labelUser.setBuddy(self.uiLineEditUser)
        self.labelSubject.setBuddy(self.uiComboSubject)
        self.labelProject.setBuddy(self.uiListProjects)
        self.labelProcedure.setBuddy(self.uiListProcedures)
        self.labelTask.setBuddy(self.uiComboTask)
        self.labelSettings.setBuddy(self.scrollArea)

        self.retranslateUi(wizard)
        self.tabWidget.setCurrentIndex(0)
        QtCore.QMetaObject.connectSlotsByName(wizard)

    def retranslateUi(self, wizard):
        _translate = QtCore.QCoreApplication.translate
        wizard.setWindowTitle(_translate("wizard", "IBLRIG Wizard"))
        self.labelUser.setText(_translate("wizard", "&User"))
        self.uiLineEditUser.setStatusTip(_translate("wizard", "Enter your user name"))
        self.uiLineEditUser.setPlaceholderText(_translate("wizard", "not logged in"))
        self.uiPushButtonLogIn.setStatusTip(_translate("wizard", "Click to log user into Alyx"))
        self.uiPushButtonLogIn.setText(_translate("wizard", "Log In"))
        self.labelSubject.setText(_translate("wizard", "&Subject"))
        self.uiComboSubject.setStatusTip(_translate("wizard", "Choose a subject"))
        self.lineEditSubject.setStatusTip(_translate("wizard", "Filter subjects by name"))
        self.lineEditSubject.setPlaceholderText(_translate("wizard", "Filter"))
        self.labelProject.setText(_translate("wizard", "&Project"))
        self.uiListProjects.setStatusTip(_translate("wizard", "Select one or several projects"))
        self.labelProcedure.setText(_translate("wizard", "P&rocedure"))
        self.uiListProcedures.setStatusTip(_translate("wizard", "Select one or several procedures"))
        self.labelTask.setText(_translate("wizard", "&Task"))
        self.uiComboTask.setStatusTip(_translate("wizard", "Select a task for the session"))
        self.labelSettings.setText(_translate("wizard", "Settings"))
        self.uiGroupTools.setTitle(_translate("wizard", "Tools"))
        self.uiPushFlush.setStatusTip(_translate("wizard", "Click to flush the Bpod\'s valve"))
        self.uiPushFlush.setText(_translate("wizard", " &Flush Valve  "))
        self.uiPushReward.setStatusTip(_translate("wizard", "Click to grant a free reward"))
        self.uiPushReward.setText(_translate("wizard", " Fr&ee Reward"))
        self.uiPushStatusLED.setStatusTip(_translate("wizard", "Click to toggle the Bpod\'s status LED"))
        self.uiPushStatusLED.setText(_translate("wizard", " Status &LED   "))
        self.uiGroupSessionControl.setTitle(_translate("wizard", "Session Control"))
        self.uiCheckAppend.setStatusTip(_translate("wizard", "append to previous session"))
        self.uiCheckAppend.setText(_translate("wizard", "Append"))
        self.uiPushStart.setStatusTip(_translate("wizard", "Click to start the session"))
        self.uiPushStart.setText(_translate("wizard", "Start"))
        self.uiPushPause.setStatusTip(_translate("wizard", "Click to pause the session after the current trial"))
        self.uiPushPause.setText(_translate("wizard", "Pause"))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tabSession), _translate("wizard", "Session"))
        self.uiMenuTools.setTitle(_translate("wizard", "Tools"))
        self.uiActionTrainingLevelV7.setText(_translate("wizard", "Get Training Level"))
        self.uiActionCalibrateFrame2ttl.setText(_translate("wizard", "Calibrate Frame2TTL"))
        self.uiActionCalibrateValve.setText(_translate("wizard", "Calibrate Valve"))
        self.uiActionValidateHardware.setText(_translate("wizard", "Validate System"))
from iblrig.gui.tools import LineEditAlyxUser
from iblrig.gui import resources_rc


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    wizard = QtWidgets.QMainWindow()
    ui = Ui_wizard()
    ui.setupUi(wizard)
    wizard.show()
    sys.exit(app.exec_())
