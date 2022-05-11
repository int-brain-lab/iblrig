#!/usr/bin/env python
# @Author: Niccolò Bonacchi
import unittest


class TestIBLRigImports(unittest.TestCase):
    def setUp(self):
        pass

    def test_iblrig_imports(self):
        # List of all import statements in iblrig on dev 20200609
        import iblutil.io.params as lib_params  # noqa
        import one.params as oneparams  # noqa
        from one.api import ONE  # noqa

    def tearDown(self):
        pass


if __name__ == "__main__":
    unittest.main(exit=False)
