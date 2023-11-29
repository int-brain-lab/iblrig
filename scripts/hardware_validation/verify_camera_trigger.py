import types
from pathlib import Path
from time import time

import iblrig.base_tasks
from pybpodapi.protocol import Bpod, StateMachine

last_time = time()


def softcode_handler(self, data):
    global last_time
    now = time()
    d = 1 / (now - last_time)
    last_time = now
    print(f'{d:.2f} Hz')


file_settings = Path(iblrig.__file__).parents[1].joinpath('settings', 'hardware_settings.yaml')
hardware_settings = iblrig.path_helper.load_settings_yaml(file_settings)
bpod = Bpod(hardware_settings['device_bpod']['COM_BPOD'], disable_behavior_ports=[1, 2, 3])
bpod.softcode_handler_function = types.MethodType(softcode_handler, bpod)

sma = StateMachine(bpod)
sma.set_global_timer(1, 5)
sma.add_state(
    state_name='start',
    state_timer=0,
    state_change_conditions={'Tup': 'wait'},
    output_actions=[('GlobalTimerTrig', 1), ('PWM1', 0)],
)
sma.add_state(
    state_name='wait',
    state_timer=0,
    state_change_conditions={'Port1In': 'flash', 'GlobalTimer1_End': 'exit'},
    output_actions=[('PWM1', 0)],
)
sma.add_state(
    state_name='flash',
    state_timer=0.001,
    state_change_conditions={'Tup': 'wait', 'GlobalTimer1_End': 'exit'},
    output_actions=[('PWM1', 255), ('SoftCode', 1)],
)

bpod.send_state_machine(sma)
bpod.run_state_machine(sma)

bpod.manual_override(2, 'PWM', 1, 0)
bpod.close()
