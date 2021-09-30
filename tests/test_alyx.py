import unittest

from one.api import ONE

import iblrig.alyx as alyx  # noqa

one = ONE(
    base_url="https://test.alyx.internationalbrainlab.org",
    username="test_user",
    password="TapetesBloc18",
)


class TestAlyx(unittest.TestCase):
    def setUp(self):
        self.one = one
        # Create fake session
        # needs:
        #     valid settings file
        #     valid mouse name
        #     valid user
        #     valid taskData for ntrials

    def test_create_session(self):
        # alyx.create_session(session_folder, one=self.one)
        pass

    def tearDown(self):
        pass


if __name__ == "__main__":
    unittest.main(exit=False)
