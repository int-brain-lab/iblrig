from pathlib import Path
import tempfile
import unittest

from iblrig_tasks._iblrig_tasks_trainingChoiceWorld.task import Session
from iblrig.test.base import TASK_KWARGS
from iblrig.transfer_experiments import SessionCopier, VideoCopier, EphysCopier


class TestSpacer(unittest.TestCase):

    def test_behavior_ephys_video_copy(self):
        with tempfile.TemporaryDirectory() as td:
            """
            First create a behavior session
            """
            iblrig_settings = {
                'iblrig_local_data_path': Path(td).joinpath('behavior'),
                'iblrig_remote_data_path': Path(td).joinpath('remote'),
            }
            session = Session(iblrig_settings=iblrig_settings, **TASK_KWARGS)
            session.create_session()
            # SESSION_RAW_DATA_FOLDER is the one that gets copied
            folder_session_video = Path(td).joinpath('video', 'Subjects', *session.paths.SESSION_FOLDER.parts[-3:])
            folder_session_ephys = Path(td).joinpath('ephys', 'Subjects', *session.paths.SESSION_FOLDER.parts[-3:])

            """
            Create an ephys acquisition
            """
            for i in range(2):
                pname = f"_spikeglx_ephysData_g0_t0.imec{str(i)}"
                folder_probe = folder_session_ephys.joinpath('raw_ephys_data', '_spikeglx_ephysData_g0', pname)
                folder_probe.mkdir(parents=True)
                for suffix in ['.ap.meta', '.lf.meta', '.ap.bin', '.lf.bin']:
                    folder_probe.joinpath(f"{pname}{suffix}").touch()
            folder_session_ephys.joinpath('raw_ephys_data', '_spikeglx_ephysData_g0',
                                          '_spikeglx_ephysData_g0_t0.imec0.nidq.bin').touch()
            folder_session_ephys.joinpath('raw_ephys_data', '_spikeglx_ephysData_g0',
                                          '_spikeglx_ephysData_g0_t0.imec0.nidq.meta').touch()
            """
            Create a video acquisition
            """
            folder_session_video.joinpath('raw_video_data').mkdir(parents=True)
            for vname in ['body', 'left', 'right']:
                folder_session_video.joinpath('raw_video_data', f'_iblrig_{vname}Camera.frameData.bin').touch()
                folder_session_video.joinpath('raw_video_data', f'_iblrig_{vname}Camera.raw.avi').touch()
            """
            Test the copiers
            """
            sc = SessionCopier(session_path=session.paths.SESSION_FOLDER,
                               remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER)
            assert sc.glob_file_remote_copy_status().suffix == '.status_pending'
            assert sc.get_copy_state()[0] == 1
            sc.copy_collections()
            assert sc.glob_file_remote_copy_status().suffix == '.status_complete'
            assert sc.get_copy_state()[0] == 2
            sc.copy_collections()
            assert sc.get_copy_state()[0] == 2

            vc = VideoCopier(session_path=folder_session_video, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER)
            assert vc.get_copy_state()[0] == 0
            vc.initialize_experiment()
            assert vc.get_copy_state()[0] == 1
            vc.copy_collections()
            assert vc.get_copy_state()[0] == 2

            ec = EphysCopier(session_path=folder_session_ephys, remote_subjects_folder=session.paths.REMOTE_SUBJECT_FOLDER)
            assert ec.get_copy_state()[0] == 0
            ec.initialize_experiment()
            assert ec.get_copy_state()[0] == 1
            ec.copy_collections()
            assert ec.get_copy_state()[0] == 2
