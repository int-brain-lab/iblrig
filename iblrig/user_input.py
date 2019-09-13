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
            label='Current weight for {}:')
        self._probe00Label = ControlLabel('Probe 00')
        self._probe01Label = ControlLabel('Probe 01')
        self._probe00X = ControlText('[X] M/L (µm):', default='0',
                                     helptext='Right = Positive, Left = Negative')
        self._probe00Y = ControlText('[Y] A/P (µm):', default='0',
                                     helptext='Anterior = Positive, Posterior = Negative')
        self._probe00Z = ControlText('[Z] D/V (µm):', default='0',
                                     helptext='Dorsal = Positive, Ventral = Negative')
        self._probe00A = ControlText(
            'Azimuth (deg):', default='0',
            helptext='Right = 0º, Front = 90º, Left = 180º/-180º, Back = -90, Range(-180º, +180º)')
        self._probe00E = ControlText('Elevation (deg):', default='0',
                                     helptext='Up = +90º, Down = -90º, Range(-90, +90)')
        self._probe00D = ControlText('[D]epth (µm):', default='0',
                                     helptext='D value of the tip.')
        self._probe00Origin = ControlCombo('Origin:')
        self._probe00Origin.add_item('', None)
        self._probe00Origin.add_item('Bregma', 'bregma')
        self._probe00Origin.add_item('Lambda', 'lambda')

        self._probe01X = ControlText('[X] M/L (µm):', default='0',
                                     helptext='Right = Positive, Left = Negative')
        self._probe01Y = ControlText('[Y] A/P (µm):', default='0',
                                     helptext='Anterior = Positive, Posterior = Negative')
        self._probe01Z = ControlText('[Z] D/V (µm):', default='0',
                                     helptext='Dorsal = Positive, Ventral = Negative')
        self._probe01A = ControlText(
            'Azimuth (deg):', default='0',
            helptext='Right = 0º, Front = 90º, Left = 180º/-180º, Back = -90, Range(-180º, +180º)')
        self._probe01E = ControlText('Elevation (deg):', default='0',
                                     helptext='Up = +90º, Down = -90º, Range(-90, +90)')
        self._probe01D = ControlText('[D]epth (µm):', default='0', helptext='D value of the tip.')
        self._probe01Origin = ControlCombo('Origin:')
        self._probe01Origin.add_item('', None)
        self._probe01Origin.add_item('Bregma', 'bregma')
        self._probe01Origin.add_item('Lambda', 'lambda')

        self._button = ControlButton('Submit')

        # Define the organization of the forms
        self.formset = [(' ', ' ', ' ', ' ', ' '),
                        (' ', '_mouseWeight', ' ', ' ', ' '),
                        (' ', '_probe00Label', ' ', '_probe01Label', ' '),
                        (' ', '_probe00Origin', ' ', '_probe01Origin', ' '),
                        (' ', '_probe00X', ' ', '_probe01X', ' '),
                        (' ', '_probe00Y', ' ', '_probe01Y', ' '),
                        (' ', '_probe00Z', ' ', '_probe01Z', ' '),
                        (' ', '_probe00A', ' ', '_probe01A', ' '),
                        (' ', '_probe00E', ' ', '_probe01E', ' '),
                        (' ', '_probe00D', ' ', '_probe01D', ' '),
                        (' ', ' ', ' ', ' ', ' '),
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
                if any([x in k for x in 'XYZAED']):
                    self.form_data.update({k: float(v)})
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
                              geometry=(200, 200, 500, 400))
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


def get_subject_weight(form_data):
    return form_data['mouseWeight']


def get_probe_data(form_data):
    return {k: v for k, v in form_data.items() if 'probe' in k and 'Label' not in k}


if __name__ == "__main__":
    res = -1
    while res == -1:
        res = session_form(mouse_name='myMouse')
    w = get_subject_weight(res)
    p = get_probe_data(res)
    print('.')
