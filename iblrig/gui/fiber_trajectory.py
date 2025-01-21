# -------------------------------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------------------------------

import json
import sys

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import (
    QApplication,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from iblatlas.atlas import AllenAtlas, Insertion
from ibllib.tests import TEST_DB
from one.webclient import AlyxClient
from iblqt.core import QAlyx
from iblqt.widgets import AlyxLoginDialog

from iblrig.path_helper import load_pydantic_yaml
from iblrig.pydantic_definitions import RigSettings

# -------------------------------------------------------------------------------------------------
# Global variables
# -------------------------------------------------------------------------------------------------

ACTUAL_DB = {
    'base_url': 'https://alyx.internationalbrainlab.org',
    'username': 'USERNAME',
    'password': 'PASSWORD',
}


# -------------------------------------------------------------------------------------------------
# Plotting functions
# -------------------------------------------------------------------------------------------------


def plot_trajectories(ax, names, trajectories, atlas=None):
    assert atlas
    top = atlas.top
    extent = np.hstack((atlas.bc.xlim, atlas.bc.ylim))
    ax.imshow(top, extent=extent, cmap='Greys_r')
    ax.set_xlim(atlas.bc.xlim)
    ax.set_ylim(atlas.bc.ylim)

    prop_cycle = plt.rcParams['axes.prop_cycle']
    colors = prop_cycle.by_key()['color']
    eps = 0.0001
    for name, traj, color in zip(names, trajectories, colors):
        x = traj[0, 0]
        y = traj[0, 1]
        if x == y == 0:
            continue
        ax.plot(traj[:, 0], traj[:, 1])
        ax.plot([x], [y], 'o', color=color)
        ax.text(x - eps, y - 4 * eps, name, color=color)


# -------------------------------------------------------------------------------------------------
# Trajectory loader
# -------------------------------------------------------------------------------------------------


class TrajectoryLoader:
    def __init__(self, atlas=None):
        self.alyx = AlyxClient(**TEST_DB)
        # self.alyx = AlyxClient(**ACTUAL_DB)
        self.atlas = atlas

    def _save_rest(self, n, v='read', pk=None):
        d = self.alyx.rest(n, v, id=pk)
        with open(f'{n}.json', 'w') as f:
            json.dump(d, f, indent=1)

    def save_subject(self, pk):
        self._save_rest(self, 'subjects', pk=pk)

    def save_session(self, pk):
        self._save_rest(self, 'sessions', pk=pk)

    def save_insertion(self, pk):
        self._save_rest(self, 'insertions', pk=pk)

    def save_trajectories(self):
        self._save_rest(self, 'trajectories', v='list')

    def create(self, name, path):
        with open(path) as f:
            self.alyx.rest(name, 'create', data=json.load(f))

    def get_trajectory(self, chronic_insertion):
        # retrieve planned/micromanip (priority) trajectory of chronic insertion
        trajectories = self.alyx.rest('trajectories', 'list', chronic_insertion=chronic_insertion)
        if not trajectories:
            return
        priorities = {
            'Planned': 1,
            'Micro-manipulator': 2,
        }
        trajectory = sorted(trajectories, key=lambda t: priorities.get(t['provenance'], 0))[-1]
        ins = Insertion.from_dict(trajectory, brain_atlas=self.atlas)
        return np.vstack((ins.entry, ins.tip))

    def get_trajectories(self, subject):
        chronic_insertions = self.alyx.rest('chronic-insertions', 'list', subject=subject, model='fiber')
        names = [i['name'] for i in chronic_insertions]
        trajectories = [self.get_trajectory(i['id']) for i in chronic_insertions]
        return names, trajectories


# -------------------------------------------------------------------------------------------------
# GUI
# -------------------------------------------------------------------------------------------------


class MainWindow(QMainWindow):
    def __init__(
        self,
        nickname: str | None = None,
        names: list[str] | None = None,
        trajectories: np.typing.NDArray[np.float64] | None = None,
        parent: QWidget | None = None,
        alyx: QAlyx | None = None,
    ):
        super().__init__(parent)

        settings: RigSettings = load_pydantic_yaml(RigSettings)
        if isinstance(alyx, QAlyx):
            self.alyx = alyx
        else:
            self.alyx = QAlyx(base_url=settings.ALYX_URL.unicode_string(), parent=self)

        # if not self.alyx.client.is_logged_in:
        #     dlg = AlyxLoginDialog(alyx=self.alyx, parent=self)
        #     dlg.setWindowTitle('Log in to Alyx')
        #     dlg.exec()

        self.atlas = AllenAtlas(25)
        self.atlas.compute_surface()

        self.nickname = nickname
        self.names = names
        self.trajectories = trajectories

        self.setWindowTitle('Fiber Insertions')

        # Main widget
        main_widget = QWidget()
        main_layout = QVBoxLayout()

        # Top panel
        top_panel = QWidget()
        top_layout = QVBoxLayout()

        # First row: Label
        label_subject = QLabel(self.nickname)
        top_layout.addWidget(label_subject)

        # Second row: Label and Textbox
        self.textboxes = []
        prop_cycle = plt.rcParams['axes.prop_cycle']
        colors = prop_cycle.by_key()['color']
        for i in range(len(self.trajectories)):
            color = colors[i]
            self.textboxes.append(QLineEdit())
            rl = QFormLayout()
            c = self.trajectories[i][0]  # 0 is entry point, 1 is tip
            s = f'{self.names[i]}: AP {c[0]:.4f}, ML {c[1]:.4f}, DV {c[2]:.4f}'
            label = QLabel(s)
            palette = label.palette()
            palette.setColor(QPalette.WindowText, QColor(color))
            label.setPalette(palette)
            rl.addRow(label, self.textboxes[i])

            top_layout.addLayout(rl)

        top_panel.setLayout(top_layout)

        # Bottom panel
        bottom_panel = QWidget()
        bottom_layout = QVBoxLayout()

        # Matplotlib figure
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)

        bottom_layout.addWidget(self.canvas)
        bottom_panel.setLayout(bottom_layout)

        # Add panels to the main layout
        main_layout.addWidget(top_panel)
        main_layout.addWidget(bottom_panel)
        main_layout.setStretch(0, 0)
        main_layout.setStretch(1, 1)

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        plot_trajectories(self.ax, self.names, self.trajectories, atlas=self.atlas)


if __name__ == '__main__':
    fig, ax = plt.subplots(1, 1)

    # subject = 'd69bacb2-5ac0-40ac-9be9-98f2fb97d858'
    # session = '66f6e1f0-a4a2-4a18-9588-38cf31377fd4'
    # probe_insertion = '59538275-27fd-4d56-9658-0c956b0e7c6f'
    # chronic_insertion = '0d5c77db-51b7-47f2-aef2-2655520731a0'
    # trajectory_estimate = 'f0925fd5-22b3-472d-b43a-d3bb91f33502'
    # nickname = 'KM_012'
    # birth_date = '2023-08-30'
    # lab = 'cortexlab'

    # Mock data
    nickname = 'CQ004'
    names = ['NBM', 'PPT']
    # NOTE: the unit should be meter, but the trajectory numbers below were given in millimeters
    # hence the `*1e-3`
    trajectories = [
        np.array([[-0.70, +1.75, -4.15], [+0.70, -1.75, +4.15]]) * 1e-3,
        np.array([[-4.72, -1.25, -2.75], [+4.72, +1.25, +2.75]]) * 1e-3,
    ]

    app = QApplication(sys.argv)
    window = MainWindow(nickname, names, trajectories)
    window.show()
    sys.exit(app.exec_())

    # from PyQt5 import QtWidgets
    # from iblrig.gui.wizard import RigWizard
    # app = QtWidgets.QApplication(['', '--no-sandbox'])
    # app.setStyle('Fusion')
    # w = RigWizard(alyx=alyx, test_subject_name='KM_012')
    # w.show()
    # app.exec()
