#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Wednesday, September 12th 2018, 3:25:44 pm
from pybpodapi.protocol import Bpod
import numpy as np
import os
import json


def get_reading(bpod_instance, save_to=None):
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

    if save_to is not None:
        data = {k: v.tolist() for k, v in Measures.items()}
        with open(os.path.join(save_to,
                               '_iblrig_ambientSensorData.raw.jsonable'),
                  'a') as f:
            f.write(json.dumps(data))
            f.write('\n')

    return {k: v.tolist()[0] for k, v in Measures.items()}


if __name__ == '__main__':
    from pybpodgui_api.models import project
    root = '/home/nico/Projects/IBL/github/iblrig/scratch'
    path = root + '/test_iblrig_params/IBL'
    p = project.Project()
    try:
        p.load(path)
    except TypeError as blabla:
        print('PyBpod says:', blabla)
        pass
    my_bpod = Bpod(serial_port=p.boards[0].serial_port)
    data = get_reading(my_bpod)
    print(data)
    my_bpod.close()
