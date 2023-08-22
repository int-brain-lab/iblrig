from pathlib import Path
from typing import Literal

from iblrig.transfer_experiments import SessionCopier
from iblrig.path_helper import load_settings_yaml


class posthoc_stubs(object):
    def __init__(self, rig_type: Literal['video', 'ephys']) -> None:

        # load settings from yaml
        self.hw_settings = load_settings_yaml('hardware_settings.yaml')
        self.rig_settings = load_settings_yaml('iblrig_settings.yaml')

        self.rig_name = self.hw_settings["RIG_NAME"]

        self.dir_local = Path(self.rig_settings['iblrig_local_data_path']).joinpath(
            self.rig_settings['ALYX_LAB'] or '', 'Subjects')

        self.dir_remote = (Path(self.rig_settings['iblrig_remote_data_path']).joinpath(
            'Subjects') if self.rig_settings['iblrig_remote_data_path'] else None)

        pass

# all_subjects = sorted([f.name for f in local_folder.glob('*') if f.is_dir()])

a = posthoc_stubs('video')