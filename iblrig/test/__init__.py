from pathlib import Path
from ibllib.tests import TEST_DB  # noqa

path_fixtures = Path(__file__).parent.joinpath('fixtures')

TASK_KWARGS = {
    'iblrig_settings': 'iblrig_settings_template.yaml',
    'hardware_settings': 'hardware_settings_template.yaml',
    'subject': 'iblrig_test_subject',
    'interactive': False,
}
