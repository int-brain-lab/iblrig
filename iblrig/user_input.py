# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Friday, May 17th 2019, 9:21:19 am
import logging
import sys

import pyforms
from AnyQt.QtWidgets import QApplication
from pyforms.basewidget import BaseWidget
from pyforms.controls import (ControlButton, ControlCombo, ControlLabel,
                              ControlText)

log = logging.getLogger('iblrig')


class SessionForm(BaseWidget):
    def __init__(self):
        super(SessionForm, self).__init__('Session info')
        # Definition of the forms fields
        self._mouseWeight = ControlText(
            label='Please insert the name of the mouse:')
        self._probeLeftLabel = ControlLabel('Probe LEFT')
        self._probeRightLabel = ControlLabel('Probe RIGHT')
        self._probeLeftX = ControlText('X:', default='0')
        self._probeLeftY = ControlText('Y:', default='0')
        self._probeLeftZ = ControlText('Z:', default='0')
        self._probeLeftD = ControlText('D:', default='0')
        self._probeLeftAngle = ControlText('Angle:', default='0')
        self._probeLeftOrigin = ControlCombo('Origin:')
        self._probeLeftOrigin.add_item('', None)
        self._probeLeftOrigin.add_item('Bregma', 'bregma')
        self._probeLeftOrigin.add_item('Lambda', 'lambda')

        self._probeRightX = ControlText('X:', default='0')
        self._probeRightY = ControlText('Y:', default='0')
        self._probeRightZ = ControlText('Z:', default='0')
        self._probeRightD = ControlText('D:', default='0')
        self._probeRightAngle = ControlText(label='Angle:', default='0')
        self._probeRightOrigin = ControlCombo('Origin:')
        self._probeRightOrigin.add_item('', None)
        self._probeRightOrigin.add_item('Bregma', 'bregma')
        self._probeRightOrigin.add_item('Lambda', 'lambda')

        self._button = ControlButton('Submit')

        # Define the organization of the forms
        self.formset = [(' ', ' ', ' ', ' ', ' '),
                        (' ', '_mouseWeight', ' ', ' ', ' '),
                        (' ', '_probeLeftLabel', ' ', '_probeRightLabel', ' '),
                        (' ', '_probeLeftX', ' ', '_probeRightX', ' '),
                        (' ', '_probeLeftY', ' ', '_probeRightY', ' '),
                        (' ', '_probeLeftZ', ' ', '_probeRightZ', ' '),
                        (' ', '_probeLeftD', ' ', '_probeRightD', ' '),
                        (' ', '_probeLeftAngle', ' ', '_probeRightAngle', ' '),
                        (' ', '_probeLeftOrigin', ' ', '_probeRightOrigin', ' '),
                        (' ', '_button', ' '),
                        (' ', ' ', ' ', ' ', ' ')]
        # The ' ' is used to indicate that a empty space should be placed at the bottom of the win
        # If you remove the ' ' the forms will occupy the entire window

        # Define the button action
        self._button.value = self.__buttonAction

        self.form_data: dict = {}
        self.valid_form_data: bool = False

    def validate_form_data_types(self):
        try:
            for k, v in self.form_data.items():
                if any([x in k for x in 'XYZD']):
                    self.form_data.update({k: float(v)})
                elif 'Angle' in k:
                    self.form_data.update({k: int(v)})
                elif 'Origin' in k:
                    self.form_data.update({k: str(v)})
                elif 'Weight' in k:
                    self.form_data.update({k: float(v)})
            self.valid_form_data = True
            return
        except Exception:
            self.valid_form_data = False
            return

    def __buttonAction(self):
        """Button action event"""
        self.form_data = {
            k.strip('_'): v.value for k, v in self.__dict__.items()
            if 'probe' in k or 'session' in k or 'Weight' in k
        }
        self.validate_form_data_types()
        self.close()
        log.info(self.form_data)
        self.app_main_window.close()
        return


def session_form(mouse_name: str = '') -> dict:
    root = QApplication(sys.argv)
    sForm = pyforms.start_app(SessionForm, parent_win=root,
                              geometry=(400, 400, 400, 200))
    sForm._mouseWeight.label = f'Current weight for {mouse_name}:'
    root.exec()

    if sForm.valid_form_data:
        return sForm.form_data
    else:
        return session_form(mouse_name)


def parse_form_data(sph):
    fdata = sph.FORM_DATA
    sph.SUBJECT_WEIGHT = fdata['mouseWeight']
    sph.LEFT_PROBE = {k: v for k, v in fdata.items() if 'Left' in k}
    sph.RIGHT_PROBE = {k: v for k, v in fdata.items() if 'Right' in k}
    return sph


# Execute the application
if __name__ == "__main__":
    bla = session_form(mouse_name='myMouse')
    print('.')
