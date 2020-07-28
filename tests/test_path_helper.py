import unittest
import iblrig.path_helper as ph
from pathlib import Path


class TestPathHelper(unittest.TestCase):
    def setUp(self):
        pass

    def test_get_iblrig_folder(self):
        f = ph.get_iblrig_folder()
        self.assertTrue(isinstance(f, str))
        self.assertTrue('iblrig' in f)

    def test_get_iblrig_params_folder(self):
        f = ph.get_iblrig_params_folder()
        self.assertTrue(isinstance(f, str))
        self.assertTrue('iblrig_params' in f)
        fp = Path(f)
        self.assertTrue(str(fp.parent) == str(Path(ph.get_iblrig_folder()).parent))

    def test_get_iblrig_data_folder(self):
        df = ph.get_iblrig_data_folder(subjects=False)
        self.assertTrue(isinstance(df, str))
        self.assertTrue('iblrig_data' in df)
        self.assertTrue('Subjects' not in df)
        dfs = ph.get_iblrig_data_folder(subjects=True)
        self.assertTrue(isinstance(dfs, str))
        self.assertTrue('iblrig_data' in dfs)
        self.assertTrue('Subjects' in dfs)

    def tearDown(self):
        pass


if __name__ == "__main__":
    unittest.main(exit=False)




