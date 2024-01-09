import unittest
from pathlib import Path

from iblrig.pydantic_definitions import BunchModel, RigSettings


class TestBunchModel(unittest.TestCase):
    def test_dict_behavior(self):
        class TestModel(BunchModel):
            person: str | None
            number: float

        test_dict1 = {'person': 'Joe', 'number': 42}
        test_dict2 = {'person': 'Zoe'}

        test_model = TestModel.model_validate(test_dict1)
        self.assertEqual(test_model.get('person'), 'Joe')
        self.assertEqual(test_model['person'], 'Joe')
        test_model['person'] = 'John'
        self.assertEqual(test_model['person'], 'John')
        test_model.update(test_dict2)
        self.assertEqual(test_model.person, 'Zoe')
        test_model.setdefault('person', 'jack')
        self.assertEqual(test_model.person, 'Zoe')
        self.assertIn('person', test_model)

        test_model = TestModel.model_validate(test_dict1)
        self.assertEqual(len(test_dict1), len(test_model))
        self.assertEqual(list(test_dict1.keys()), list(test_model.keys()))
        self.assertEqual(list(test_dict1.values()), list(test_model.values()))
        self.assertEqual(list(test_dict1.items()), list(test_model.items()))
        self.assertEqual(list(iter(test_dict1)), list(iter(test_model)))

        with self.assertRaises(NotImplementedError):
            del test_model['person']
        with self.assertRaises(NotImplementedError):
            test_model.pop('person')
        with self.assertRaises(NotImplementedError):
            test_model.popitem()
        with self.assertRaises(NotImplementedError):
            test_model.clear()


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
