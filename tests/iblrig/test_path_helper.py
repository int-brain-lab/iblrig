import iblrig.path_helper as ph
from pathlib import Path


def test_get_iblrig_folder():
    f = ph.get_iblrig_folder()
    assert(isinstance(f, str))
    assert('iblrig' in f)


def test_get_iblrig_params_folder():
    f = ph.get_iblrig_params_folder()
    assert(isinstance(f, str))
    assert('iblrig_params' in f)
    fp = Path(f)
    assert(str(fp.parent) == str(Path(ph.get_iblrig_folder()).parent))


def test_get_iblrig_data_folder():
    df = ph.get_iblrig_data_folder(subjects=False)
    assert(isinstance(df, str))
    assert('iblrig_data' in df)
    assert('Subjects' not in df)
    dfs = ph.get_iblrig_data_folder(subjects=True)
    assert(isinstance(dfs, str))
    assert('iblrig_data' in dfs)
    assert('Subjects' in dfs)
