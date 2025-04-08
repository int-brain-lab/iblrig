import unittest
from collections.abc import Callable
from importlib.metadata import entry_points


class TestEntryPoints(unittest.TestCase):
    def test_entry_points(self) -> None:
        for ep in [ep for ep in entry_points(group='console_scripts') if ep.value.startswith('iblrig.')]:
            loaded_ep = ep.load()  # this throws a ModuleNotFound error if the entry-point is invalid
            assert isinstance(loaded_ep, Callable)
