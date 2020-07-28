import unittest

from ibllib.one import ONE

import iblrig.alyx as alyx

one = ONE(
    base_url="https://test.alyx.internationalbrainlab.org",
    username="test_user",
    password="TapetesBloc18",
)


class TestAlyx(unittest.TestCase):
    def setUp(self):
        self.one = one

    def test_create_session(self):
        alyx.create_session(session_folder, one=self.one)

    def tearDown(self):
        pass


if __name__ == "__main__":
    unittest.main(exit=False)
