from iblrig.base_tasks import BpodMixin, SoundMixin
from iblrig.constants import BASE_PATH
from pybpodapi.protocol import StateMachine


class _SoundCheckTask(BpodMixin, SoundMixin):
    protocol_name = 'hardware_check_harp'

    def __init__(self, *args, **kwargs):
        param_file = BASE_PATH.joinpath('iblrig', 'base_choice_world_params.yaml')
        super().__init__(*args, task_parameter_file=param_file, **kwargs)

    def start_hardware(self):
        self.start_mixin_bpod()
        self.start_mixin_sound()

    def get_state_machine(self):
        sma = StateMachine(self.bpod)
        sma.add_state('tone', 0.5, {'Tup': 'noise'}, [self.bpod.actions.play_tone])
        sma.add_state('noise', 1, {'Tup': 'exit'}, [self.bpod.actions.play_noise])
        return sma

    def play_sounds(self):
        sma = self.get_state_machine()
        self.bpod.send_state_machine(sma)
        self.bpod.run_state_machine(sma)

    def _run(self):
        pass


def sound_check():
    """
    # TODO: within the task (and actually with this hardware check), we need to test
     for the exact same number of pulses than generated by the state machine.
    # if it is more, it means it's noise and potentially disconnected, if it is less,
     it means the sound card is not sending the pulses properly

    bpod_data_success:
        GPIO -- Bpod OR GPIO X- Bpod
        Harp -- Bpod
        GPIO -- Harp

    bpod_data_success
    {'Bpod start timestamp': 0.620611,
     'Trial start timestamp': 0.620611,
     'Trial end timestamp': 2.120613,
     'States timestamps': {'play_tone': [(0, 0.5)], 'error': [(0.5, 1.5)]},
     'Events timestamps': {'BNC2High': [0.0007, 0.5007],
      'BNC2Low': [0.1107, 1.0007000000000001],
      'Tup': [0.5, 1.5]}}

    bpod_data_failure:
        GPIO -- Bpod
        Harp -X Bpod
        GPIO -X Harp
    {'Bpod start timestamp': 0.620611,
     'Trial start timestamp': 232.963811,
     'Trial end timestamp': 234.463814,
     'States timestamps': {'play_tone': [(0, 0.5)], 'error': [(0.5, 1.5)]},
     'Events timestamps': {'BNC2Low': [0.008400000000000001,
       0.0349,
       0.08990000000000001,
       0.1796,
       0.19360000000000002,
       0.2753,
       0.28150000000000003,
       0.29550000000000004,
       0.33140000000000003,
       0.36100000000000004,
       0.5086,
       0.5457000000000001,
       0.6646000000000001,
       0.6959000000000001,
       0.7241000000000001,
       0.8599,
       0.8823000000000001,
       0.9087000000000001,
       0.9398000000000001,
       1.0050000000000001,
       1.1079,
       1.1265,
       1.1955,
       1.2302,
       1.3635000000000002,
       1.4215],
      'BNC2High': [0.0085,
       0.035,
       0.09000000000000001,
       0.1797,
       0.1937,
       0.27540000000000003,
       0.2816,
       0.29560000000000003,
       0.3315,
       0.36110000000000003,
       0.5087,
       0.5458000000000001,
       0.6647000000000001,
       0.6960000000000001,
       0.7242000000000001,
       0.86,
       0.8824000000000001,
       0.9088,
       0.9399000000000001,
       1.0051,
       1.108,
       1.1266,
       1.1956,
       1.2303,
       1.3636000000000001,
       1.4216],
      'Tup': [0.5, 1.5]}}

    bpod data failure: case if sound card is not wired properly (no feedback from sound card)
    bpod_data_failure:
        GPIO -X Bpod
        Harp -X Bpod
        GPIO -- Harp
    Out[49]:
    {'Bpod start timestamp': 0.620611,
     'Trial start timestamp': 405.619411,
     'Trial end timestamp': 407.119414,
     'States timestamps': {'play_tone': [(0, 0.5)], 'error': [(0.5, 1.5)]},
     'Events timestamps': {'Tup': [0.5, 1.5]}}
    """

    task = _SoundCheckTask(subject='toto')
    task.start_hardware()
    task.play_sounds()

    bpod_data = task.bpod.session.current_trial.export()
    assert len(bpod_data['Events timestamps']['BNC2High']) == 2