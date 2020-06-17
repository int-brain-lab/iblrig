import unittest

import iblrig.alyx as alyx
from ibllib.one import ONE

one = ONE(base_url='https://test.alyx.internationalbrainlab.org', username='test_user',
          password='TapetesBloc18')


class TestAlyx(unittest.TestCase):
    def setUp(self):
        self.one = one

    def test_create_session(self):
        pass

    def tearDown(self):
        pass
