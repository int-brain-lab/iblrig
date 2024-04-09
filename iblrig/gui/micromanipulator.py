# convert_uis *micro*
import argparse

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as Canvas
from PyQt5 import QtCore, QtWidgets

from iblatlas.atlas import NeedlesAtlas
from iblrig.ephys import neuropixel24_micromanipulator_coordinates
from iblrig.gui.ui_micromanipulator import Ui_MainWindow
from iblrig.gui.models import MicroManipulatorModel

matplotlib.use('QT5Agg')


class GuiMicroManipulator(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, **kwargs):
        super().__init__()
        self.setupUi(self)
        self.model = MicroManipulatorModel()
        self.atlas = NeedlesAtlas()
        self.uiMpl.canvas.fig.tight_layout()
        self.uiPush_np24.clicked.connect(self.on_push_np24)
        self.uiPush_show.clicked.connect(self.on_push_show)
        self.update_view()
        self.make_plots()
        self.uiMpl.canvas.fig.tight_layout()

    def make_plots(self):
        """
        This recreates the plots for the top view and the slice view.
        """
        self.uiMpl.canvas.ax[0].clear()
        self.atlas.plot_top(ax=self.uiMpl.canvas.ax[0])
        self.uiMpl.canvas.ax[0].plot(self.model.trajectory.x, self.model.trajectory.y, '>', color='k')
        for shank, traj in self.model.trajectories.items():
            self.uiMpl.canvas.ax[0].plot(traj['x'], traj['y'], 'xr', label=shank)
            self.uiMpl.canvas.ax[0].text(traj['x'], traj['y'], shank[-1], color='w', fontweight=800)
        # update slice
        self.uiMpl.canvas.ax[1].clear()
        if self.model.trajectory.get_slice_type() == 'coronal':
            self.atlas.plot_cslice(ap_coordinate=self.model.trajectory.y / 1e6, ax=self.uiMpl.canvas.ax[1], volume='annotation')
            for shank, traj in self.model.trajectories.items():
                self.uiMpl.canvas.ax[1].plot(traj['x'], traj['z'], 'xr', label=shank)
                self.uiMpl.canvas.ax[1].text(traj['x'], traj['z'], shank[-1], color='w', fontweight=800)
        elif self.model.trajectory.get_slice_type() == 'sagittal':
            self.atlas.plot_sslice(ml_coordinate=self.model.trajectory.x / 1e6, ax=self.uiMpl.canvas.ax[1], volume='annotation')
            for shank, traj in self.model.trajectories.items():
                self.uiMpl.canvas.ax[1].plot(traj['y'], traj['z'], 'xr', label=shank)
                self.uiMpl.canvas.ax[1].text(traj['y'], traj['z'], shank[-1], color='w', fontweight=800)
        else:  # if the validation yields nothing, plot a sagittal slice by default
            self.atlas.plot_sslice(ml_coordinate=0, ax=self.uiMpl.canvas.ax[1], volume='annotation')
        self.uiMpl.canvas.draw()

    def update_view(self):
        self.uiLine_x.setText(str(self.model.trajectory.x))
        self.uiLine_y.setText(str(self.model.trajectory.y))
        self.uiLine_z.setText(str(self.model.trajectory.z))
        self.uiLine_phi.setText(str(self.model.trajectory.phi))
        self.uiLine_depth.setText(str(self.model.trajectory.depth))
        self.uiLine_theta.setText(str(self.model.trajectory.theta))

    def update_model(self):
        self.model.trajectory.x = float(self.uiLine_x.text())
        self.model.trajectory.y = float(self.uiLine_y.text())
        self.model.trajectory.z = float(self.uiLine_z.text())
        self.model.trajectory.phi = float(self.uiLine_phi.text())
        self.model.trajectory.depth = float(self.uiLine_depth.text())
        self.model.trajectory.theta = float(self.uiLine_theta.text())

    def on_push_np24(self):
        self.model.trajectories = neuropixel24_micromanipulator_coordinates(
            self.model.trajectory.__dict__(), self.model.pname, ba=self.atlas
        )
        self.make_plots()

    def on_push_show(self):
        self.make_plots()


class MplCanvas(Canvas):
    """
    Matplotlib canvas class to create figure
    """

    def __init__(self):
        self.fig, self.ax = plt.subplots(1, 2, gridspec_kw={'width_ratios': [1, 2]})
        Canvas.__init__(self, self.fig)
        Canvas.setSizePolicy(self, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        Canvas.updateGeometry(self)


class MplWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)  # Inherit from QWidget
        self.canvas = MplCanvas()  # Create canvas object
        self.vbl = QtWidgets.QVBoxLayout()  # Set box for plotting
        self.vbl.addWidget(self.canvas)
        self.setLayout(self.vbl)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('subject')
    args = parser.parse_args()
    QtCore.QCoreApplication.setOrganizationName('International Brain Laboratory')
    QtCore.QCoreApplication.setOrganizationDomain('internationalbrainlab.org')
    QtCore.QCoreApplication.setApplicationName('IBLRIG MicroManipulator')

    app = QtWidgets.QApplication(['', '--no-sandbox'])
    app.setStyle('Fusion')
    w = GuiMicroManipulator(subject=args.subject)
    w.show()
    app.exec()


if __name__ == '__main__':
    main()
