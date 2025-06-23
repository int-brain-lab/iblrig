import unittest
from pathlib import Path

import pytest

from iblrig.pydantic_definitions import BunchModel, RigSettings


class ExampleModel(BunchModel):
    name: str
    age: int


class TestBunchModel:
    @pytest.fixture
    def test_model(self):
        return ExampleModel(name='Alice', age=30)

    def test_getitem(self, test_model):
        assert test_model['name'] == 'Alice'
        assert test_model['age'] == 30

    def test_setitem(self, test_model):
        test_model['name'] = 'Bob'
        assert test_model['name'] == 'Bob'
        test_model['age'] = 25
        assert test_model['age'] == 25

    def test_len(self, test_model):
        assert len(test_model) == 2  # name and age

    def test_iter(self, test_model):
        keys = list(test_model)
        assert keys == ['name', 'age']

    def test_items(self, test_model):
        items = test_model.items()
        assert list(items) == [('name', 'Alice'), ('age', 30)]

    def test_keys(self, test_model):
        keys = test_model.keys()
        assert list(keys) == ['name', 'age']

    def test_values(self, test_model):
        values = list(test_model.values())
        assert values == ['Alice', 30]

    def test_del_not_implemented(self, test_model):
        with pytest.raises(NotImplementedError):
            del test_model['name']

    def test_pop_not_implemented(self, test_model):
        with pytest.raises(NotImplementedError):
            test_model.pop('name')

    def test_popitem_not_implemented(self, test_model):
        with pytest.raises(NotImplementedError):
            test_model.popitem()

    def test_clear_not_implemented(self, test_model):
        with pytest.raises(NotImplementedError):
            test_model.clear()

    def test_invalid_model(self):
        with pytest.raises(ValueError):
            ExampleModel(name='Alice', age='not_an_integer')  # age should be an int


class TestRigSettings(unittest.TestCase):
    def test_validators(self):
        my_dict = {
            'iblrig_local_data_path': Path.cwd(),
            'iblrig_remote_data_path': None,
            'ALYX_USER': 'Joe',
            'ALYX_URL': 'https://server.com',
            'ALYX_LAB': 'my_lab',
        }
        rig_settings = RigSettings.model_validate(my_dict)

        with self.assertRaises(ValueError):
            rig_settings.ALYX_USER = 'John Doe'
        with self.assertRaises(ValueError):
            rig_settings.iblrig_remote_data_path = True
