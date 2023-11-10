import unittest
from importlib.metadata import entry_points
from typing import Callable


class TestEntryPoints(unittest.TestCase):

    def test_entry_points(self) -> None:
        """
        Test iblrig's console_scripts entry points

        The method collects the names and loaded entry points of iblrig scripts
        and performs assertions or checks based on the loaded entry points.

        Raises:
            AssertionError: If loaded entry points are not callable.
        """
        iblrig_scripts = []
        for ep in entry_points(group='console_scripts'):
            if ep.value.startswith('iblrig.'):
                try:
                    loaded_ep = ep.load()
                    iblrig_scripts.append((ep.name, loaded_ep))
                except Exception as e:
                    print(f"Error loading entry point '{ep.name}': {str(e)}")

        assert all(isinstance(script[1], Callable) for script in iblrig_scripts), "Loaded entry points are not callable."
