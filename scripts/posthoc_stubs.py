from pathlib import Path
from re import search
from os import walk
import sys

from ibllib.io import session_params
from iblrig.transfer_experiments import VideoCopier, EphysCopier
from iblrig.path_helper import load_settings_yaml
from deploy import videopc, ephyspc


class posthoc_stubs(object):
    def __init__(self, stub_file: str) -> None:

        # pick relevant options for ephys/video data (identified by name of stub-file)
        if search(r'^cameras_.+\.yaml', stub_file):
            self.stub_file = Path(videopc.__file__).parent.joinpath('device_stubs', stub_file)
            self.copier = VideoCopier
            self.type = 'video'
        elif search(r'^neuropixel_.+\.yaml', stub_file):
            self.stub_file = Path(ephyspc.__file__).parent.joinpath('device_stubs', stub_file)
            self.copier = EphysCopier
            self.type = 'ephys'
        if not hasattr(self, 'stub_file') or not self.stub_file.exists():
            valid_options = [x[2] for x in walk(Path(videopc.__file__).parent.joinpath('device_stubs'))][0]
            valid_options.extend([x[2] for x in walk(Path(ephyspc.__file__).parent.joinpath('device_stubs'))][0])
            print(f"Invalid device stub name: '{stub_file}'", file=sys.stderr)
            print("Valid options are:", file=sys.stderr)
            [print(f"- '{x}'", file=sys.stderr) for x in sorted(valid_options)]
            sys.exit(1)

        self.daq_description = session_params.read_params(self.stub_file)
        self.rig_settings = load_settings_yaml('iblrig_settings.yaml')

        self.dir_local = Path(self.rig_settings['iblrig_local_data_path']).joinpath(
            self.rig_settings['ALYX_LAB'] or '', 'Subjects')
        if not self.dir_local.exists():
            raise Exception(f"Cannot find local directory: {self.dir_local}")

        self.dir_remote = (Path(self.rig_settings['iblrig_remote_data_path']).joinpath(
            'Subjects') if self.rig_settings['iblrig_remote_data_path'] else None)
        if not self.dir_remote.exists():
            raise Exception(f"Cannot find remote directory: {self.dir_remote}")

        # sorted list of unique raw data folders
        dir_raw = sorted(list({Path(i[0]).parent for i in walk(self.dir_local) if i[0].endswith('raw_video_data')}))
        self.dir_raw = [d for d in dir_raw if self.copier(d, self.dir_remote).get_state()[0] == 0]

    def preview(self):
        print('The following sessions will be copied:')
        [print(f"- '{x}'") for x in self.dir_raw]

    def upload(self):
        for session_path in self.dir_raw:
            vc = self.copier(session_path=session_path, remote_subjects_folder=self.dir_remote)
            vc.prepare_experiment()
            vc.copy_collection()
            print(vc.state()[1])
