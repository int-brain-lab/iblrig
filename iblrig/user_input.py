# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Friday, May 17th 2019, 9:21:19 am
import logging
import sys

import ibllib.graphic as graph
import pyforms
from AnyQt.QtWidgets import QApplication
from oneibl.one import ONE
from pyforms.basewidget import BaseWidget
from pyforms.controls import (ControlButton, ControlCheckBox, ControlLabel,
                              ControlText)

from iblrig.misc import patch_settings_file

log = logging.getLogger("iblrig")


class SessionForm(BaseWidget):
    def __init__(self):
        super(SessionForm, self).__init__("Session info")
        # Definition of the forms fields
        self._mouseWeight = ControlText(label="Current weight for {}:")

        self._probe00Label = ControlLabel("Probe 00")
        self._probe01Label = ControlLabel("Probe 01")

        self._probe00X = ControlText(
            "X [M/L] (µm):", default="0", helptext="Right = Positive, Left = Negative"
        )
        self._probe00Y = ControlText(
            "Y [A/P] (µm):",
            default="0",
            helptext="Anterior = Positive, Posterior = Negative",
        )
        self._probe00Z = ControlText(
            "Z [D/V] (µm):",
            default="0",
            helptext="Dorsal = Positive, Ventral = Negative",
        )
        self._probe00P = ControlText(
            "θ [polar angle] (deg):",
            default="0",
            helptext="0º vertical 90º horizontal, Range(0º, 180º)",
        )
        self._probe00A = ControlText(
            "φ [azimuth] (deg):",
            default="0",
            helptext="Right = 0º, Front = 90º, Left = 180º/-180º, Back = -90, Range(-180º, +180º)",
        )
        self._probe00T = ControlText(
            "β [tilt] (deg):",
            default="0",
            helptext="0º flat facing vertical axis [Z], Range(-180º, 180º)",
        )
        self._probe00D = ControlText(
            "D [deρth] (µm):", default="0", helptext="D value of the tip."
        )
        self._probe00BregmaLabel = ControlLabel("Origin:")
        self._probe00Bregma = ControlCheckBox("bregma", True)
        self._probe00Bregma.value = True
        self._probe00alternateOrigin = ControlText(
            "Alternate origin:",
            default="",
            helptext='To be filled only if origin is not bregma, e.g. "lambda"',
        )

        self._probe01X = ControlText(
            "X [M/L] (µm):", default="0", helptext="Right = Positive, Left = Negative"
        )
        self._probe01Y = ControlText(
            "Y [A/P] (µm):",
            default="0",
            helptext="Anterior = Positive, Posterior = Negative",
        )
        self._probe01Z = ControlText(
            "Z [D/V] (µm):",
            default="0",
            helptext="Dorsal = Positive, Ventral = Negative",
        )
        self._probe01P = ControlText(
            "θ [polar angle] (deg):",
            default="0",
            helptext="0º vertical 90º horizontal, Range(0º, 180º)",
        )
        self._probe01A = ControlText(
            "φ [azimuth] (deg):",
            default="0",
            helptext="Right = 0º, Front = 90º, Left = 180º/-180º, Back = -90, Range(-180º, +180º)",
        )
        self._probe01T = ControlText(
            "β [tilt] (deg):",
            default="0",
            helptext="0º flat facing vertical axis [Z], Range(-180º, 180º)",
        )
        self._probe01D = ControlText(
            "D [deρth] (µm):", default="0", helptext="D value of the tip."
        )
        self._probe01BregmaLabel = ControlLabel("Origin:")
        self._probe01Bregma = ControlCheckBox("bregma", True)
        self._probe01Bregma.value = True
        self._probe01alternateOrigin = ControlText(
            "Alternate origin:",
            default="",
            helptext='To be filled only if origin is not bregma, e.g. "lambda"',
        )

        self._button = ControlButton("Submit")

        # Define the organization of the forms
        self.formset = [
            (" ", " ", " ", " ", " "),
            (" ", "_mouseWeight", " ", " ", " "),
            (" ", "_probe00Label", " ", "_probe01Label", " "),
            (" ", "_probe00X", " ", "_probe01X", " "),
            (" ", "_probe00Y", " ", "_probe01Y", " "),
            (" ", "_probe00Z", " ", "_probe01Z", " "),
            (" ", "_probe00P", " ", "_probe01P", " "),
            (" ", "_probe00A", " ", "_probe01A", " "),
            (" ", "_probe00T", " ", "_probe01T", " "),
            (" ", "_probe00D", " ", "_probe01D", " "),
            (" ", " ", " ", " ", " "),
            (
                " ",
                "_probe00BregmaLabel",
                "_probe00Bregma",
                " ",
                "_probe01BregmaLabel",
                "_probe01Bregma",
                " ",
            ),
            (" ", "_probe00alternateOrigin", " ", "_probe01alternateOrigin", " "),
            (" ", " ", " ", " ", " "),
            (" ", "_button", " "),
            (" ", " ", " ", " ", " "),
        ]
        # The ' ' is used to indicate that a empty space should be placed at the bottom of the win
        # If you remove the ' ' the forms will occupy the entire window

        # Define the button action
        self._button.value = self.__buttonAction

        self.form_data: dict = {}
        self.valid_form_data: bool = False

    def validate_form_data_types(self):
        try:
            for k, v in self.form_data.items():
                if any([x in k for x in "XYZPATD"]):
                    self.form_data.update({k: float(v)})
                elif "Weight" in k:
                    self.form_data.update({k: float(v)})
            self.valid_form_data = True
            return
        except Exception:
            self.valid_form_data = False
            return

    def __buttonAction(self):
        """Button action event"""
        self.form_data = {
            k.strip("_"): v.value
            for k, v in self.__dict__.items()
            if "probe" in k or "Weight" in k
        }
        self.validate_form_data_types()
        self.close()
        log.info(self.form_data)
        self.app_main_window.close()
        return


def session_form(mouse_name: str = "") -> dict:
    root = QApplication(sys.argv)
    sForm = pyforms.start_app(
        SessionForm, parent_win=root, geometry=(200, 200, 600, 400)
    )
    sForm._mouseWeight.label = sForm._mouseWeight.label.format(mouse_name)
    root.exec()

    if sForm.valid_form_data:
        return sForm.form_data
    else:
        return -1
        # sForm.close()
        # sForm.destroy()
        # root.quit()
        # return session_form(mouse_name)


def get_form_subject_weight(form_data: dict) -> float:
    return form_data["mouseWeight"]


def get_form_probe_data(form_data: dict) -> dict:
    flat = {k: v for k, v in form_data.items() if "probe" in k and "Label" not in k}
    nested = {"probe00": {}, "probe01": {}}
    for k in flat:
        if "probe00" in k:
            nk = k.strip("probe00")
            nk = nk[0].capitalize() + nk[1:]
            nested["probe00"][nk] = flat[k]
        elif "probe01" in k:
            nk = k.strip("probe01")
            nk = nk[0].capitalize() + nk[1:]
            nested["probe01"][nk] = flat[k]

    return nested


def ask_subject_weight(subject: str, settings_file_path: str = None) -> float:
    out = graph.numinput(
        "Subject weighing (gr)", f"{subject} weight (gr):", nullable=False
    )
    log.info(f"Subject weight {out}")
    if settings_file_path is not None:
        patch = {"SUBJECT_WEIGHT": out}
        patch_settings_file(settings_file_path, patch)
    return out


def ask_session_delay(settings_file_path: str = None) -> int:
    out = graph.numinput(
        "Session delay",
        "Delay session initiation by (min):",
        default=0,
        minval=0,
        maxval=60,
        nullable=False,
        askint=True,
    )
    out = out * 60
    if settings_file_path is not None:
        patch = {"SESSION_START_DELAY_SEC": out}
        patch_settings_file(settings_file_path, patch)
    return out


def ask_is_mock(settings_file_path: str = None) -> bool:
    out = None
    resp = graph.strinput(
        "Session type",
        "IS this a MOCK recording? (yes/NO)",
        default="NO",
        nullable=True,
    )
    if resp is None:
        return ask_is_mock(settings_file_path)
    if resp.lower() in ["no", "n", ""]:
        out = False
    elif resp.lower() in ["yes", "y"]:
        out = True
    else:
        return ask_is_mock(settings_file_path)
    if settings_file_path is not None and out is not None:
        patch = {"IS_MOCK": out}
        patch_settings_file(settings_file_path, patch)
    return out


def ask_confirm_session_idx(session_idx):
    # Confirm this is the session to load with user. If not override SESSION_IDX
    sess_num = int(session_idx + 1)
    sess_num = graph.numinput(
        "Confirm session to load",
        "Load recording session number",
        default=sess_num,
        askint=True,
        minval=1,
        maxval=12,
    )
    if sess_num != session_idx + 1:
        session_idx = sess_num - 1
    return session_idx


def ask_project(subject_name, one=None):
    if subject_name == '_iblrig_test_mouse':
        log.info(f"Test mouse detected Project for {subject_name}: _iblrig_test_project")
        return '_iblrig_test_project'
    one = one or ONE()
    projects = one.alyx.rest('subjects', 'read', subject_name)['session_projects']
    if not projects:
        log.info(f"No Projects found for Subject {subject_name}: []")
        return None
    elif len(projects) == 1:
        log.info(f"One project found for subject {subject_name}: [{projects[0]}]")
        return projects[0]
    else:
        log.info(f"Multiple projects found for subject {subject_name}:{projects}")
        last_sessions = one.search(subject=subject_name, limit=10)
        last_project = one.alyx.rest("sessions", "read", last_sessions[0])['project']
        title = 'Select Project'
        prompt = str(projects)
        default = last_project
        out_proj = graph.strinput(
            title, prompt, default=default, nullable=True
        )
        if out_proj not in projects:
            return ask_project(subject_name, one=one)
        return out_proj


if __name__ == "__main__":
    # settings_file_path = '/home/nico/Projects/IBL/github/iblrig_data/Subjects/_iblrig_fake_subject/2019-09-25/002/raw_behavior_data/_iblrig_taskSettings.raw.json'  # noqa
    # delay = ask_session_delay(settings_file_path)
    # mock = ask_is_mock()
    # res = -1
    # while res == -1:
    #     res = session_form(mouse_name="myMouse")
    # w = get_form_subject_weight(res)
    # p = get_form_probe_data(res)
    # print(f"Weight: {w}", f"\nProbe data: {p}")

    subject_name = 'CSHL046'
    proj = ask_project(subject_name, one=None)
    print(proj)
    print(".")
