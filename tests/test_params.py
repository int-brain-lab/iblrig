import unittest

import iblrig.params as params


class TestParams(unittest.TestCase):
    def setUp(self):
        self.loaded_params = None

    def test_ensure_all_keys_present(self):
        out = params.ensure_all_keys_present(params.EMPTY_BOARD_PARAMS)
        print(out)
        1
    def tearDown(self):
        pass


if __name__ == "__main__":
    unittest.main(exit=False)
