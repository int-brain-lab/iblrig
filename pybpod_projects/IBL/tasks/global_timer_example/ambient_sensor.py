# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Wednesday, September 12th 2018, 3:25:44 pm
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 12-09-2018 03:26:03.033
from pybpodapi.protocol import Bpod
import numpy as np


def get_reading(bpod_instance):
    ambient_module = [x for x in bpod_instance.modules
                      if x.name == 'AmbientModule1'][0]
    ambient_module.start_module_relay()
    bpod_instance.bpod_modules.module_write(ambient_module, 'R')
    reply = bpod_instance.bpod_modules.module_read(ambient_module, 12)
    ambient_module.stop_module_relay()

    Measures = {'Temperature_C': np.frombuffer(bytes(reply[:4]), np.float32),
                'AirPressure_mb': np.frombuffer(bytes(reply[4:8]),
                                                np.float32) / 100,
                'RelativeHumidity': np.frombuffer(bytes(reply[8:]), np.float32)
                }

    return Measures


if __name__ == '__maii__':
    my_bpod = Bpod()
    data = get_reading(my_bpod)