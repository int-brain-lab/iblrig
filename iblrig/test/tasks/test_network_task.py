import unittest

from iblutil.io import net

from iblrig.test.base import TASK_KWARGS, BaseTestCases
from iblrig.base_tasks import NetworkMixin
from iblrig.test.tasks.test_biased_choice_world_family import get_fixtures
from iblrig_tasks._iblrig_tasks_trainingChoiceWorld.task import Session as TrainingChoiceWorldSession
from iblrig_tasks._iblrig_tasks_trainingPhaseChoiceWorld.task import Session as TrainingPhaseChoiceWorldSession


class NetworkSession(TrainingChoiceWorldSession, NetworkMixin):
    pass


class TestNetworkTask(unittest.TestCase):
    """Test a situation where the main sync is on a different computer."""
    def setUp(self):
        lan_ip = net.base.hostname2ip()  # Local area network IP of this PC
        remote_uri = net.base.validate_uri(lan_ip, default_port=9998)

        self.task = NetworkSession(**TASK_KWARGS, remote_rigs={'neuropixel': remote_uri})

    def test_something(self):
        self.assertEqual(True, False)  # add assertion here


if __name__ == '__main__':
    unittest.main()
