import unittest


class TestIBLRigImports(unittest.TestCase):

    def setUp(self):
        pass

    def test_iblrig_imports(self):
        # List of all import statements in iblrig on dev 20200609
        import ibllib.graphic as graph  # noqa
        import ibllib.io.flags as flags  # noqa
        import ibllib.io.params as lib_params  # noqa
        import ibllib.io.raw_data_loaders as raw  # noqa
        import ibllib.pipes.misc as misc  # noqa
        import oneibl.params  # noqa
        from ibllib.dsp.smooth import rolling_window as smooth  # noqa
        from ibllib.graphic import numinput, popup, strinput  # noqa
        from ibllib.io import raw_data_loaders as raw  # noqa
        from ibllib.misc import logger_config  # noqa
        from ibllib.pipes.purge_rig_data import purge_local_data  # noqa
        from ibllib.pipes.transfer_rig_data import main  # noqa
        from oneibl.one import ONE  # noqa
        from oneibl.registration import RegistrationClient  # noqa

    def tearDown(self):
        pass


if __name__ == "__main__":
    unittest.main(exit=False)
