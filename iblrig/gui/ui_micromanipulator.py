
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

TRAJECTORY_KEYS = ['x', 'y', 'z', 'depth', 'theta', 'phi', 'roll']
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
    roll: float = Field(..., ge=-180, le=360, title='Roll (deg)')
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

        # compute button
        compute_button = QtWidgets.QPushButton("Compute")
        compute_button.clicked.connect(self.compute)
        form_layout.addWidget(compute_button, 1, len(self.column_keys) + 1)

        # clear button
        clear_button = QtWidgets.QPushButton("Clear")
        clear_button.clicked.connect(self.clear_table)
        form_layout.addWidget(clear_button, 1, len(self.column_keys) + 2)

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
                _traj = {k:trajectory[k] for k in TRAJECTORY_KEYS}
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
            # the pivot shank is shown in black
            line = self.canvas.axes1.plot(x, y, 'x', label=pname)[0]
            line_color = line.get_color()
            if x.size > 1:
                self.canvas.axes1.plot(x[0], y[0], 'xk')
            i = 0
            for _, rec in shanks_trajectories.iterrows():
                # set the pivot shank in black bold if multishank
                if (i == 0) and (x.size > 1):
                    self.canvas.axes1.text(xlabels[i], ylabels[i], rec.shank, color='k', fontweight=1000)
                else:
                    self.canvas.axes1.text(xlabels[i], ylabels[i], rec.shank, color=line_color, fontweight=800)
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
        """
        Read and validate all probe insertion trajectories from the table widget.

        This method performs a comprehensive extraction and validation of all probe insertion
        trajectory data currently displayed in the GUI table widget. It systematically iterates
        through each row of the table, collecting data from all columns, and then validates
        each complete row against the ProbeInsertion Pydantic model to ensure data integrity
        and type correctness before returning the results.

        The method follows a multi-step process:
        1. Iterates through all rows in the table widget (self.table)
        2. For each row, creates a dictionary by extracting text from each cell
        3. Maps the extracted text to the appropriate field keys defined in self.column_keys
        4. Validates the complete row data using the ProbeInsertion Pydantic model
        5. Converts the validated model instance to a dictionary representation
        6. Appends the validated dictionary to the results list

        The validation step ensures that all trajectory parameters meet the required constraints:
        - pname: Must be a valid string without special characters or spaces. This is enforced
                 by a custom validator that uses a regular expression to check for alphanumeric
                 characters, underscores, and hyphens only. Examples of valid names: "probe00",
                 "probe_01", "left-hemisphere-probe". Invalid names: "probe 00" (contains space),
                 "probe#1" (contains special character).
        - x, y, z, depth: Must be valid floating-point numbers representing coordinates in micrometers.
                          These values are automatically converted from string to float during validation.
                          The coordinate system follows the standard stereotaxic convention where:
                          * x (mediolateral): negative = right hemisphere, positive = left hemisphere
                          * y (anteroposterior): relative to bregma, positive = anterior, negative = posterior
                          * z (dorsoventral): relative to brain surface, positive = ventral, negative = dorsal
        - theta: Must be between -90 and 90 degrees (elevation angle). This represents the angle
                 of the probe in the coronal plane. A value of 0 degrees means the probe is horizontal,
                 positive values indicate the probe tip is tilted dorsally (upward), and negative values
                 indicate ventral tilt (downward). Typical values range from 0 to 15 degrees for most
                 insertions to avoid major blood vessels.
        - phi: Must be between -180 and 360 degrees (azimuth angle). This represents the angle of
               the probe in the horizontal plane. A value of 0 degrees points anteriorly (toward the
               front of the brain), 90 degrees points to the left, 180/-180 degrees points posteriorly,
               and 270 degrees points to the right. The extended range (-180 to 360) allows for
               flexibility in angle specification.
        - roll: Must be between -180 and 360 degrees (roll angle). This represents rotation around
                the probe's longitudinal axis. For multi-shank probes like the Neuropixels 2.4, this
                determines the orientation of the shanks relative to the brain's anatomical axes.
                A value of 0 degrees typically means the shanks are aligned with the coronal plane.
        - shanks: Must be an integer between 1 and 4 (number of probe shanks). This field is
                  particularly important for Neuropixels 2.4 probes which can have up to 4 shanks.
                  Single-shank probes (like Neuropixels 1.0 or 2.0) should have a value of 1.

        This method is typically called when the user needs to:
        - Register probe trajectories with the Alyx database: After planning multiple probe insertions,
          the user clicks the "Register" button, which calls this method to collect all trajectories
          before sending them to the database.
        - Update the visualization plots with current trajectory data: When the user adds or modifies
          a trajectory, the update_plots() method calls read_table() to get the current state of all
          trajectories for rendering on the brain atlas visualization.
        - Export trajectory data for further processing: Users may want to save their planned trajectories
          to a file for documentation or sharing with collaborators.
        - Validate all current entries before performing batch operations: Before executing any operation
          that depends on trajectory data, this method ensures all entries are valid and properly formatted.

        Returns
        -------
        list of dict
            A list of dictionaries, where each dictionary represents a validated probe insertion
            trajectory. Each dictionary contains the following keys:

            - 'pname' (str): The probe name identifier, must not contain spaces or special characters.
                             This name is used as a unique identifier for the probe and will be used
                             in the Alyx database and in file naming conventions. It should be descriptive
                             but concise. Common naming conventions include:
                             * Sequential numbering: "probe00", "probe01", "probe02"
                             * Anatomical location: "left_striatum", "right_hippocampus"
                             * Shank identification: "probe00a", "probe00b" (for multi-shank probes)

            - 'x' (float): The mediolateral (ML) coordinate in micrometers, where negative values
                           indicate right hemisphere and positive values indicate left hemisphere.
                           This coordinate is measured from the midline (sagittal suture) of the skull.
                           Typical values range from -5000 to +5000 micrometers for mouse brain.
                           Example: x = -2243.5 means the probe entry point is 2243.5 μm to the right
                           of the midline.

            - 'y' (float): The anteroposterior (AP) coordinate in micrometers relative to bregma.
                           Bregma is the anatomical landmark where the coronal and sagittal sutures meet.
                           Positive values indicate positions anterior to bregma, negative values indicate
                           posterior positions. Typical values range from -5000 to +3000 micrometers for
                           mouse brain. Example: y = -4131.3 means the probe entry point is 4131.3 μm
                           posterior to bregma.

            - 'z' (float): The dorsoventral (DV) coordinate in micrometers relative to the brain surface.
                           This is typically measured from the dura mater (the outermost membrane covering
                           the brain). Positive values indicate depth below the surface, negative values
                           would indicate positions above the surface (which is unusual in practice).
                           Typical values range from 0 to 5000 micrometers depending on the target depth.
                           Example: z = 901.1 means the probe entry point is 901.1 μm below the brain surface.

            - 'depth' (float): The insertion depth in micrometers from the entry point. This represents
                               how far the probe will be inserted along its trajectory from the entry point
                               at the brain surface. This is different from the z-coordinate, which is the
                               vertical depth. The actual depth along the probe trajectory depends on the
                               angles (theta and phi). For a vertical insertion (theta=0, phi=0), depth
                               would equal the z-coordinate change. Typical values range from 2000 to 5000
                               micrometers. Example: depth = 3300.7 means the probe tip will be 3300.7 μm
                               from the entry point along the probe's trajectory.

            - 'theta' (float): The elevation angle in degrees, constrained between -90 and 90 degrees,
                              where 0 degrees is horizontal and positive values tilt dorsally (upward).
                              This angle is measured in the coronal plane (the plane perpendicular to the
                              anteroposterior axis). A positive theta means the probe is angled such that
                              the tip is more dorsal (higher) than the entry point. Most insertions use
                              small positive angles (5-15 degrees) to avoid major blood vessels on the
                              brain surface. Example: theta = 15 means the probe is tilted 15 degrees
                              from horizontal, with the tip pointing dorsally.

            - 'phi' (float): The azimuth angle in degrees, constrained between -180 and 360 degrees,
                            where 0 degrees points anteriorly and angles increase counterclockwise when
                            viewed from above. This angle is measured in the horizontal plane. The extended
                            range allows for flexible angle specification:
                            * 0° or 360° = anterior (toward the front)
                            * 90° = left (toward the left hemisphere)
                            * 180° or -180° = posterior (toward the back)
                            * 270° or -90° = right (toward the right hemisphere)
                            Example: phi = 270 means the probe is oriented toward the right side of the brain.

            - 'roll' (float): The roll angle in degrees, constrained between -180 and 360 degrees,
                             representing rotation around the probe's longitudinal axis. This is particularly
                             important for multi-shank probes where the orientation of the shanks relative
                             to anatomical structures matters. For single-shank probes, this value is often
                             set to 0. For multi-shank probes, different roll angles will position the shanks
                             in different orientations relative to brain structures. Example: roll = 0 means
                             the probe shanks are in their default orientation (typically aligned with the
                             coronal plane for multi-shank probes).

            - 'shanks' (int): The number of probe shanks, must be between 1 and 4, typically used
                             for multi-shank Neuropixels 2.4 probes. Single-shank probes (Neuropixels 1.0,
                             2.0, 2.1) should have shanks=1. Multi-shank Neuropixels 2.4 probes can have
                             2, 3, or 4 shanks arranged in a specific geometric pattern. When shanks > 1,
                             the compute() method will automatically calculate the individual coordinates
                             for each shank based on the probe geometry and the roll angle. Example: shanks = 4
                             indicates a 4-shank Neuropixels 2.4 probe, which will result in 4 separate
                             trajectory entries (one for each shank) being added to the table.

            The returned list maintains the same order as the rows appear in the table widget.
            If the table is empty, an empty list is returned. The order is preserved because
            it may be meaningful to the user (e.g., probes listed in order of insertion priority).

        Raises
        ------
        ValidationError
            Raised by the Pydantic ProbeInsertion model if any row in the table contains invalid
            data that doesn't conform to the model's field constraints. This can occur when:

            - Required fields are missing or empty: If any of the required fields (pname, x, y, z,
              depth, theta, phi, roll, shanks) is missing from the row_data dictionary or contains
              an empty string, Pydantic will raise a ValidationError indicating which field is missing.
              Example error: "Field required" for the missing field.

            - Numeric values cannot be converted to float or int types: If a field that expects a
              numeric value (x, y, z, depth, theta, phi, roll, shanks) contains non-numeric text,
              Pydantic will fail to convert it and raise a ValidationError. Example: if the user
              enters "abc" in the x-coordinate field, the error will indicate "Input should be a
              valid number, unable to parse string as a number".

            - Values fall outside the specified ranges: If numeric values are outside their allowed
              ranges, validation will fail. Examples:
              * theta = 95 will fail because theta must be between -90 and 90
              * phi = 400 will fail because phi must be between -180 and 360
              * shanks = 5 will fail because shanks must be between 1 and 4
              The error message will indicate the field name and the constraint that was violated.

            - The probe name contains invalid characters: If the pname field contains spaces or
              special characters (anything other than alphanumeric, underscore, or hyphen), the
              custom validator will raise a ValidationError with the message "must not contain
              spaces or special characters". Examples of invalid names: "probe 00", "probe#1",
              "probe@left".

            - Field types don't match expected types (e.g., string provided for numeric field)

            When this exception is raised, it contains detailed information about which field(s)
            failed validation and the specific reason for the failure, allowing for precise
            error reporting to the user.

        Notes
        -----
        - This method assumes that self.column_keys is properly initialized and matches the
          order of columns in the table widget
        - Empty cells (None items) are skipped during data collection, which may result in
          missing required fields and subsequent validation errors
        - The Pydantic model validation occurs for each row independently, so a validation
          error in one row will prevent the entire method from completing successfully
        - The method uses model_dump() to convert Pydantic model instances to dictionaries,
          which ensures consistent serialization of the validated data

        Examples
        --------
        Example 1: Reading trajectories from a table with a single probe insertion
        >>> # Assume the table has one row with the following data:
        >>> # pname='probe00', x=-2243.5, y=-4131.3, z=901.1, depth=3300.7,
        >>> # theta=15.0, phi=270.0, roll=0.0, shanks=1
        >>> trajectories = self.read_table()
        >>> print(f"Found {len(trajectories)} trajectory")
        Found 1 trajectory
        >>> print(f"Probe name: {trajectories[0]['pname']}")
        Probe name: probe00
        >>> print(f"Entry coordinates: x={trajectories[0]['x']}, y={trajectories[0]['y']}, z={trajectories[0]['z']}")
        Entry coordinates: x=-2243.5, y=-4131.3, z=901.1
        >>> print(f"Insertion depth: {trajectories[0]['depth']} μm")
        Insertion depth: 3300.7 μm
        >>> print(f"Angles: theta={trajectories[0]['theta']}°, phi={trajectories[0]['phi']}°, roll={trajectories[0]['roll']}°")
        Angles: theta=15.0°, phi=270.0°, roll=0.0°

        Example 2: Reading multiple probe trajectories for bilateral recording
        >>> # Assume the table has two rows:
        >>> # Row 1: pname='left_striatum', x=2500.0, y=-500.0, z=1200.0, depth=4000.0,
        >>> #        theta=10.0, phi=90.0, roll=0.0, shanks=1
        >>> # Row 2: pname='right_striatum', x=-2500.0, y=-500.0, z=1200.0, depth=4000.0,
        >>> #        theta=10.0, phi=270.0, roll=0.0, shanks=1
        >>> trajectories = self.read_table()
        >>> print(f"Found {len(trajectories)} trajectories for bilateral recording")
        Found 2 trajectories for bilateral recording
        >>> for i, traj in enumerate(trajectories, 1):
        ...     hemisphere = "left" if traj['x'] > 0 else "right"
        ...     print(f"Probe {i} ({traj['pname']}): {hemisphere} hemisphere at ML={traj['x']} μm")
        Probe 1 (left_striatum): left hemisphere at ML=2500.0 μm
        Probe 2 (right_striatum): right hemisphere at ML=-2500.0 μm

        Example 3: Reading a multi-shank Neuropixels 2.4 probe trajectory
        >>> # Assume the table has four rows representing a 4-shank probe:
        >>> # Row 1: pname='probe00a', x=-2243.5, y=-4131.3, z=901.1, depth=3300.7,
        >>> #        theta=15.0, phi=270.0, roll=0.0, shanks=1
        >>> # Row 2: pname='probe00b', x=-2443.5, y=-4131.3, z=901.1, depth=3300.7,
        >>> #        theta=15.0, phi=270.0, roll=0.0, shanks=1
        >>> # Row 3: pname='probe00c', x=-2643.5, y=-4131.3, z=901.1, depth=3300.7,
        >>> #        theta=15.0, phi=270.0, roll=0.0, shanks=1
        >>> # Row 4: pname='probe00d', x=-2843.5, y=-4131.3, z=901.1, depth=3300.7,
        >>> #        theta=15.0, phi=270.0, roll=0.0, shanks=1
        >>> trajectories = self.read_table()
        >>> print(f"Multi-shank probe with {len(trajectories)} shanks")
        Multi-shank probe with 4 shanks
        >>> # Calculate the spacing between shanks
        >>> x_coords = [traj['x'] for traj in trajectories]
        >>> spacing = abs(x_coords[1] - x_coords[0])
        >>> print(f"Shank spacing: {spacing} μm")
        Shank spacing: 200.0 μm
        >>> # Verify all shanks have the same angles and depth
        >>> angles_match = all(traj['theta'] == trajectories[0]['theta'] and
        ...                    traj['phi'] == trajectories[0]['phi'] for traj in trajectories)
        >>> print(f"All shanks aligned: {angles_match}")
        All shanks aligned: True

        Example 4: Handling an empty table
        >>> # Assume the table widget has no rows (user hasn't added any trajectories yet)
        >>> trajectories = self.read_table()
        >>> if not trajectories:
        ...     print("No trajectories found in table. Please add probe insertion data.")
        ... else:
        ...     print(f"Processing {len(trajectories)} trajectories...")
        No trajectories found in table. Please add probe insertion data.

        Example 5: Using read_table() to prepare data for Alyx registration
        >>> # This example shows how read_table() is typically used in the register() method
        >>> # Assume the table has three probes with different target regions
        >>> trajectories = self.read_table()
        >>> print(f"Preparing to register {len(trajectories)} probe trajectories with Alyx database")
        Preparing to register 3 probe trajectories with Alyx database
        >>> # Convert to the format expected by the registration function
        >>> # (dictionary with probe names as keys and trajectory parameters as values)
        >>> trajectories_dict = {t['pname']: {k: t[k] for k in TRAJECTORY_KEYS} for t in trajectories}
        >>> for probe_name, params in trajectories_dict.items():
        ...     print(f"\n{probe_name}:")
        ...     print(f"  Entry point: ({params['x']:.1f}, {params['y']:.1f}, {params['z']:.1f}) μm")
        ...     print(f"  Depth: {params['depth']:.1f} μm")
        ...     print(f"  Orientation: θ={params['theta']:.1f}°, φ={params['phi']:.1f}°, roll={params['roll']:.1f}°")

        probe00:
          Entry point: (-2243.5, -4131.3, 901.1) μm
          Depth: 3300.7 μm
          Orientation: θ=15.0°, φ=270.0°, roll=0.0°

        probe01:
          Entry point: (-3500.0, -2000.0, 1500.0) μm
          Depth: 4500.0 μm
          Orientation: θ=12.0°, φ=270.0°, roll=0.0°

        probe02:
          Entry point: (-1800.0, -3500.0, 800.0) μm
          Depth: 3800.0 μm
          Orientation: θ=18.0°, φ=270.0°, roll=0.0°

        Example 6: Iterating through trajectories to update visualization plots
        >>> # This example demonstrates how read_table() is used in update_plots()
        >>> # to refresh the brain atlas visualization with current trajectory data
        >>> trajectories = self.read_table()
        >>> print(f"Updating plots with {len(trajectories)} probe trajectories")
        Updating plots with 3 probe trajectories
        >>> # Convert to pandas DataFrame for easier grouping and analysis
        >>> import pandas as pd
        >>> df = pd.DataFrame(trajectories)
        >>> # Extract shank identifier from probe name (last character)
        >>> df['shank'] = df['pname'].apply(lambda x: x[-1])
        >>> # Extract base probe name (all but last character)
        >>> df['probe_base'] = df['pname'].apply(lambda x: x[:-1])
        >>> # Group by base probe name to handle multi-shank probes
        >>> for probe_name, shanks_df in df.groupby('probe_base'):
        ...     num_shanks = len(shanks_df)
        ...     x_range = shanks_df['x'].max() - shanks_df['x'].min()
        ...     y_range = shanks_df['y'].max() - shanks_df['y'].min()
        ...     print(f"\n{probe_name}: {num_shanks} shank(s)")
        ...     print(f"  ML range: {x_range:.1f} μm, AP range: {y_range:.1f} μm")
        ...     if num_shanks > 1:
        ...         print(f"  Multi-shank configuration detected")
        ...     else:
        ...         print(f"  Single-shank probe")

        probe00: 4 shank(s)
          ML range: 600.0 μm, AP range: 0.0 μm
          Multi-shank configuration detected

        probe01: 1 shank(s)
          ML range: 0.0 μm, AP range: 0.0 μm
          Single-shank probe

        probe02: 1 shank(s)
          ML range: 0.0 μm, AP range: 0.0 μm
          Single-shank probe

        See Also
        --------
        add_row_to_table : Method to add validated trajectory data to the table
        compute : Method that validates input and adds rows to the table
        ProbeInsertion : Pydantic model class defining the validation schema
        """
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
        trajectories = {t['pname']: {k: t[k] for k in TRAJECTORY_KEYS} for t in self.read_table()}
        print(f"Registering: Subject={subject}, Date={date_str}, Number={number}, "
              f"Serial={serial}, Version={version}")

        try:
            assert subject != '', "Subject cannot be empty"
            assert number != '', "Number cannot be empty"
            assert date_str != '', "Date cannot be empty"
            self.model.alyx.rest('subjects', 'list', nickname=subject, no_cache=True)
            if not self.model.alyx.is_logged_in:
                dlg = LoginWindow(parent=self, username=self.iblrig_settings.ALYX_USER, password='', remember=True)
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
            iblrig.ephys.register_micromanipulator_coordinates(
                alyx=self.model.alyx, trajectories=trajectories, eid=eid, metadata=None)
        except Exception as e:
            # Display validation errors to the user
            full_error_message = traceback.format_exc()
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
