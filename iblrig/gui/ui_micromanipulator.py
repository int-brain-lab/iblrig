
import sys
import re
from datetime import date
from pathlib import Path
import traceback

import numpy as np
import pandas as pd
from qtpy import QtWidgets, QtCore, QtGui
from pydantic import BaseModel, Field, field_validator, ValidationError
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas  # Fixme qt5
from matplotlib.figure import Figure

import iblrig.ephys
import one.alf.path as alfpath
import spikeglx
from iblatlas.atlas import NeedlesAtlas
from iblrig.ephys import neuropixel24_micromanipulator_coordinates
from iblrig.gui.wizard import RigWizardModel, LoginWindow
from iblrig.gui import resources_rc  # noqa: F401


default_trajectory = {'x': -1200.1, 'y': -4131.3, 'z': 901.1, 'phi': 270, 'theta': 15, 'depth': 3300.7, 'roll': 0, 'shanks': 4}

PROBE_MODELS = ('NP2.4', 'NP2.4 QB', 'NP2.1', '3B2', '3A')

class ProbeInsertion(BaseModel):
    """Pydantic model for validating probe insertion data."""
    pname: str = Field(..., title='Probe Name')
    x: float = Field(..., title='X-ML (um)')
    y: float = Field(..., title='Y-AP (um)')
    z: float = Field(..., title='Z-DV (um)')
    depth: float = Field(..., title='Depth (um)')
    theta: float = Field(..., ge=-90, le=90, title='Theta-Elevation (deg)')
    phi: float = Field(..., ge=-180, le=360, title='Phi-Azimuth (deg)')
    shanks: int = Field(..., ge=1, le=4, title='# Shanks')

    @field_validator('pname')
    @classmethod
    def pname_no_special_chars(cls, v: str) -> str:
        if not re.match(r'^[a-zA-Z0-9_-]*$', v):
            raise ValueError('must not contain spaces or special characters')
        return v


class MplCanvas(FigureCanvas):
    """Matplotlib canvas widget to embed in a Qt application."""

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes1 = self.fig.add_subplot(1, 1, 1)
        self.fig.tight_layout()
        super(MplCanvas, self).__init__(self.fig)
        self.setParent(parent)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()


        self.settings = QtCore.QSettings("IBL", "MicroManipulatorGUI")
        self.model = RigWizardModel()

        self.setWindowTitle("Micro-Manipulator GUI")
        self.setGeometry(150, 150, 1100, 900)

        self.atlas = NeedlesAtlas()

        # Main widget and layout
        main_widget = QtWidgets.QWidget(self)
        self.setCentralWidget(main_widget)
        layout = QtWidgets.QVBoxLayout(main_widget)

        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(":/images/iblrig_logo"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.setWindowIcon(icon)

        # --- Create Form on top ---
        self.line_edits = {}
        form_widget = QtWidgets.QWidget()
        form_layout = QtWidgets.QGridLayout(form_widget)

        self.column_info = {key: field.title for key, field in ProbeInsertion.model_fields.items()}
        self.column_keys = list(self.column_info.keys())
        for i, key in enumerate(self.column_keys):
            label_text = self.column_info[key]
            label = QtWidgets.QLabel(label_text)
            line_edit = QtWidgets.QLineEdit()
            default_value = str(default_trajectory.get(key, ''))
            line_edit.setText(self.settings.value(key, default_value))
            line_edit.setPlaceholderText(label_text)
            self.line_edits[key] = line_edit
            form_layout.addWidget(label, 0, i)
            form_layout.addWidget(line_edit, 1, i)

        compute_button = QtWidgets.QPushButton("Compute")
        compute_button.clicked.connect(self.compute)
        form_layout.addWidget(compute_button, 1, len(self.column_keys))

        clear_button = QtWidgets.QPushButton("Clear")
        clear_button.clicked.connect(self.clear_table)
        form_layout.addWidget(clear_button, 1, len(self.column_keys) + 1)

        # --- Create Table ---
        self.table = QtWidgets.QTableWidget(0, len(self.column_keys))  # 0 rows initially
        self.table.setHorizontalHeaderLabels([self.column_info[key] for key in self.column_keys])
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)

        # Create Matplotlib canvas
        self.canvas = MplCanvas(self, width=4, height=4, dpi=100)

        # --- Create Registration Form at the bottom ---
        self.reg_line_edits = {}
        reg_form_widget = QtWidgets.QWidget()
        reg_form_widget.setMaximumWidth(500)
        reg_form_widget.setMaximumHeight(500)
        reg_form_layout = QtWidgets.QGridLayout(reg_form_widget)
        reg_form_layout.setRowStretch(0, 1)  # Add stretch to push content down

        # Column 0: Manual mode and labels
        self.manual_mode_checkbox = QtWidgets.QCheckBox("Manual Input")
        self.manual_mode_checkbox.toggled.connect(self.toggle_manual_mode)
        reg_form_layout.addWidget(self.manual_mode_checkbox, 1, 0)

        reg_fields = {"subject": "Subject", "date": "Date", "number": "Number", "serial": "Serial", "version": "Version"}
        for i, (key, label_text) in enumerate(reg_fields.items()):
            label = QtWidgets.QLabel(label_text)
            reg_form_layout.addWidget(label, i + 2, 0)

        # Column 1: Browse button and input widgets
        self.browse_button = QtWidgets.QPushButton("AP File...")
        self.browse_button.clicked.connect(self.browse_file)
        reg_form_layout.addWidget(self.browse_button, 1, 1)

        # Subject, Date, Number LineEdits
        for i, key in enumerate(["subject", "date", "number"]):
            line_edit = QtWidgets.QLineEdit()
            if key == 'date':
                line_edit.setText(date.today().isoformat())
            self.reg_line_edits[key] = line_edit
            reg_form_layout.addWidget(line_edit, i + 2, 1)

        # Serial LineEdit
        self.reg_line_edits['serial'] = QtWidgets.QLineEdit()
        reg_form_layout.addWidget(self.reg_line_edits['serial'], 5, 1)

        # Version ComboBox
        self.probe_model_combo = QtWidgets.QComboBox()
        self.probe_model_combo.addItems(PROBE_MODELS)
        reg_form_layout.addWidget(self.probe_model_combo, 6, 1)

        # Register button below everything
        register_button = QtWidgets.QPushButton("Register")
        register_button.clicked.connect(self.register)
        reg_form_layout.addWidget(register_button, len(reg_fields) + 2, 0, 1, 2)  # Span across columns

        # Add widgets to layout
        layout.addWidget(form_widget)
        layout.addWidget(self.table)

        # Create a horizontal layout for the canvas and the registration form
        canvas_and_form_layout = QtWidgets.QHBoxLayout()
        canvas_and_form_layout.addWidget(self.canvas, 1)  # Give stretch factor of 1 to canvas
        canvas_and_form_layout.addWidget(reg_form_widget, 0, QtCore.Qt.AlignTop)  # Give stretch factor of 0 to form
        layout.addLayout(canvas_and_form_layout)

        self.init_images()
        self.toggle_manual_mode(False)  # Set initial state to non-manual

    def closeEvent(self, event):
        """Save settings when the window is closed."""
        for key, line_edit in self.line_edits.items():
            self.settings.setValue(key, line_edit.text())
        super().closeEvent(event)

    def compute(self):
        """
        Triggered by the 'Compute' button.
        Validates input fields using a Pydantic model and, if valid, adds a new row to the table.
        """
        raw_trajectory = {key: line_edit.text().strip() for key, line_edit in self.line_edits.items()}

        try:
            # Validate the data using the Pydantic model
            trajectory = ProbeInsertion(**raw_trajectory)
            trajectory = trajectory.model_dump()

            if int(raw_trajectory['shanks']) == 1:
                _traj = {k:trajectory[k] for k in ['x', 'y', 'z', 'depth', 'theta', 'phi']}
                _traj['roll'] = 0
                shanks_trajectories = {trajectory['pname']:_traj}
            else:
                shanks_trajectories = neuropixel24_micromanipulator_coordinates(
                    trajectory, pname=trajectory['pname'], ba=self.atlas)

            for k in shanks_trajectories.keys():
                shank_data = shanks_trajectories[k]
                shank_data['pname'] = k
                shank_data['shanks'] = 1
                self.add_row_to_table(shank_data)

            self.update_plots()
        except ValidationError as e:
            # Display validation errors to the user
            error_messages = []
            for error in e.errors():
                field_name = error['loc'][0]
                label = self.column_info.get(field_name, field_name)
                error_messages.append(f"Error in '{label}': {error['msg']}")
            error_dialog = QtWidgets.QMessageBox()
            error_dialog.setIcon(QtWidgets.QMessageBox.Warning)
            error_dialog.setText("Invalid input")
            error_dialog.setInformativeText("\n".join(error_messages))
            error_dialog.setWindowTitle("Validation Error")
            error_dialog.exec_()
            print("\n".join(error_messages))



    def add_row_to_table(self, data):
        """Adds a new row to the table with the given data, removing any existing rows with the same probe name."""
        # Get the probe name from the data
        probe_name = data.get('pname', '')

        # Find and remove existing rows with the same probe name
        if probe_name:
            # Get the column index for 'pname'
            pname_col_idx = self.column_keys.index('pname')

            # Iterate through rows in reverse to safely remove items
            for row in range(self.table.rowCount() - 1, -1, -1):
                item = self.table.item(row, pname_col_idx)
                if item and item.text() == probe_name:
                    self.table.removeRow(row)

        # Add the new row
        row_position = self.table.rowCount()
        self.table.insertRow(row_position)
        for i, key in enumerate(self.column_keys):
            item = QtWidgets.QTableWidgetItem(str(data.get(key, '')))
            self.table.setItem(row_position, i, item)

    def update_plots(self):
        self.clear_plots()
        df = pd.DataFrame(self.read_table())
        df['shank'] = df['pname'].apply(lambda x: x[-1])
        df['pname'] = df['pname'].apply(lambda x: x[:-1])
        for pname, shanks_trajectories in df.groupby('pname'):
            # we compute the text labels coordinates so they are legible on the overall plot
            x = shanks_trajectories['x'].values
            y = shanks_trajectories['y'].values

            # this is the angle of the labels from the x-axis positive direction, mathematical direction
            angle = np.arctan((y[-1] - y[0]) / (x[-1] - x[0]) ) - np.pi / 2
            # we dilate the labels by 2.5 and move them orthogonal to the shank alignment
            xlabels = (x - np.mean(x)) * 2.5 + 400 * np.cos(angle) + np.mean(x)
            ylabels = (y - np.mean(y)) * 2.5 + 400 * np.sin(angle) + np.mean(y)
            i = 0
            self.canvas.axes1.plot(x, y, 'x', label=pname)
            for _, rec in shanks_trajectories.iterrows():
                self.canvas.axes1.text(xlabels[i], ylabels[i], rec.shank, color='k', fontweight=800)
                i += 1
            self.canvas.axes1.legend()
            self.canvas.draw()


    def clear_plots(self):
        # Clear the lines and labels on the plot
        for ax in [self.canvas.axes1]:
            [h.remove() for h in ax.lines]
            [h.remove() for h in ax.texts]
            if ax.get_legend() is not None:
                ax.get_legend().remove()
        self.canvas.draw()

    def clear_table(self):
        """Clears all rows from the table and resets the plot."""
        self.table.setRowCount(0)
        self.clear_plots()

    def init_images(self):
        # Plot images
        self.atlas.compute_surface()
        self.atlas.plot_top(volume='image', ax=self.canvas.axes1)
        self.canvas.axes1.set_axis_off()
        self.canvas.fig.tight_layout()
        self.canvas.draw()

    def toggle_manual_mode(self, checked):
        """Enable or disable manual input fields."""
        self.browse_button.setEnabled(not checked)
        for key, widget in self.reg_line_edits.items():
            widget.setReadOnly(not checked)
            widget.setStyleSheet("background-color: lightgray;" if not checked else "")
        self.probe_model_combo.setEnabled(checked)

    def browse_file(self):
        """Opens a file dialog to select a file and populates fields from its path."""
        options = QtWidgets.QFileDialog.Options()
        start_path = str(self.model.iblrig_settings.iblrig_local_subjects_path)
        fileName, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select AP Binary File", start_path, "AP Binary Files (*.ap.*bin);;All Files (*)", options=options)
        if fileName:
            print(f"File selected: {fileName}")
            binfile = Path(fileName)
            session_path = alfpath.get_session_path(binfile)
            self.model.session_folder = session_path
            try:
                # Assumes path structure .../subject/date/number/...
                self.reg_line_edits['subject'].setText(session_path.parts[-3])
                self.reg_line_edits['date'].setText(session_path.parts[-2])
                self.reg_line_edits['number'].setText(session_path.parts[-1])
                sr = spikeglx.Reader(binfile)
                self.probe_model_combo.setCurrentText(sr.meta['neuropixelVersion'])
                self.reg_line_edits['serial'].setText(str(sr.meta['serial']))
            except IndexError:
                print("Could not parse subject/date/number from path. Please check the directory structure.")

    def read_table(self):
        trajectories = []
        for row in range(self.table.rowCount()):
            row_data = {}
            for col_idx, key in enumerate(self.column_keys):
                item = self.table.item(row, col_idx)
                if item:
                    row_data[key] = item.text()
            # Validate and format each row using the Pydantic model
            trajectory = ProbeInsertion(**row_data)
            trajectories.append(trajectory.model_dump())  # format as a dictionary for Pydantic model validation)
        return trajectories

    @property
    def iblrig_settings(self):
        return self.model.iblrig_settings

    def register(self):
        """Placeholder method for the 'Register' button action."""
        subject = self.reg_line_edits['subject'].text()
        date_str = self.reg_line_edits['date'].text()
        number = self.reg_line_edits['number'].text()
        serial = self.reg_line_edits['serial'].text()
        version = self.probe_model_combo.currentText()
        trajectories = self.read_table()
        print(f"Registering: Subject={subject}, Date={date_str}, Number={number}, "
              f"Serial={serial}, Version={version}")

        try:
            assert subject != '', "Subject cannot be empty"
            assert number != '', "Number cannot be empty"
            assert date != '', "Date cannot be empty"
            self.model.alyx.rest('subjects', 'list', nickname=subject, no_cache=True)
            if not self.model.alyx.is_logged_in:
                dlg = LoginWindow(parent=self, username='self.iblrig_settings.ALYX_USER', password='', remember=True)
                if dlg.result():
                    username = dlg.lineEditUsername.text()
                    password = dlg.lineEditPassword.text()
                    remember = dlg.checkBoxRememberMe.isChecked()
                    dlg.deleteLater()
                    self.model.alyx.authenticate(username=username, password=password, do_cache=remember)
                else:
                    raise ConnectionError('Unable to authenticate with Alyx, check your settings or internet connection')
            rest_session = self.model.alyx.rest('sessions', 'list', subject=subject, date_range=[date_str, date_str], number=number)
            if len(rest_session) == 1:
                eid = rest_session[0]['id']
            elif len(rest_session) == 0:
                raise ValueError(f"No session found for subject={subject}, date={date_str}, number={number}")
            elif len(rest_session) > 1:
                raise ValueError(f"Multiple sessions found for subject={subject}, date={date_str}, number={number}")
            iblrig.ephys.register_micromanipulator_coordinates(alyx=self.model.alyx, trajectories=trajectories, eid=None,
                                                               metadata=None)
        except Exception as e:
            # Display validation errors to the user
            full_error_message = ''.join(traceback.format_exception(e))
            error_message = str(e)
            error_dialog = QtWidgets.QMessageBox()
            error_dialog.setIcon(QtWidgets.QMessageBox.Warning)
            error_dialog.setText("Invalid input")
            error_dialog.setInformativeText(error_message)
            error_dialog.setWindowTitle("Validation Error")
            error_dialog.exec_()
            print(full_error_message)

def main():
    app = QtWidgets.QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
