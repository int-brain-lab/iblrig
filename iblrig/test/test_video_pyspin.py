import sys
from unittest import TestCase
from unittest.mock import MagicMock


class MockCameraPtr:
    pass


class MockCameraList:
    pass


class MockIEnumeration:
    pass


class MockIInteger:
    pass


class MockIFloat:
    pass


class MockIBoolean:
    pass


# Mock the PySpin module in sys.modules
mock_pyspin = MagicMock()
mock_pyspin.CameraPtr = MockCameraPtr
mock_pyspin.CameraList = MockCameraList
mock_pyspin.IEnumeration = MockIEnumeration
mock_pyspin.IInteger = MockIInteger
mock_pyspin.IFloat = MockIFloat
mock_pyspin.IBoolean = MockIBoolean
mock_pyspin.IsReadable.return_value = True
mock_pyspin.IsWritable.return_value = True
sys.modules['PySpin'] = mock_pyspin

from iblrig import video_pyspin  # noqa: E402


def get_mock_camera():
    mock_camera = MagicMock(spec=mock_pyspin.CameraPtr)
    mock_camera.DeviceID = MagicMock(return_value='123456789')
    mock_camera.TestNode = MagicMock()
    mock_camera.TestNode.GetUnit.return_value = 'MockUnit'
    mock_camera.TestNode.GetDisplayName.return_value = 'MockDisplayName'
    mock_camera.GetNodeMap = MagicMock()
    mock_camera.GetNodeMap.GetNode = MagicMock(return_value=mock_camera.TestNode)
    return mock_camera


class TestPrivateMethods(TestCase):
    def setUp(self):
        self.mock_camera = get_mock_camera()
        self.mock_node = self.mock_camera.TestNode

    def test_get_node(self):
        node = video_pyspin._get_node('TestNode', self.mock_camera)
        self.assertIs(self.mock_node, node)
        with self.assertRaises(AttributeError):
            node = video_pyspin._get_node('NonExistentNode', self.mock_camera)

    def test_get_readable_node(self):
        node = video_pyspin._get_readable_node('TestNode', self.mock_camera)
        self.assertIs(self.mock_node, node)
        mock_pyspin.IsReadable.return_value = False
        with self.assertRaises(AttributeError):
            video_pyspin._get_readable_node('TestNode', self.mock_camera)
        mock_pyspin.IsReadable.return_value = True
        delattr(self.mock_node, 'GetValue')
        with self.assertRaises(AttributeError):
            video_pyspin._get_readable_node('TestNode', self.mock_camera)

    def test_get_writable_node(self):
        node = video_pyspin._get_writable_node('TestNode', self.mock_camera)
        self.assertIs(self.mock_node, node)
        mock_pyspin.IsWritable.return_value = False
        with self.assertRaises(AttributeError):
            video_pyspin._get_writable_node('TestNode', self.mock_camera)
        mock_pyspin.IsWritable.return_value = True
        delattr(self.mock_node, 'SetValue')
        with self.assertRaises(AttributeError):
            video_pyspin._get_writable_node('TestNode', self.mock_camera)


class TestGetStringValue(TestCase):
    def setUp(self):
        self.mock_camera = get_mock_camera()
        self.mock_node = self.mock_camera.TestNode

    def test_get_string_value_integer_node(self):
        self.mock_node.__class__ = mock_pyspin.IInteger
        self.mock_node.GetValue.return_value = 42
        (result,) = video_pyspin.get_string_value('TestNode', self.mock_camera)
        self.assertEqual('42 MockUnit', result)

    def test_get_string_value_enumeration_node(self):
        self.mock_node.__class__ = mock_pyspin.IEnumeration
        mock_entry = MagicMock()
        mock_entry.GetDisplayName.return_value = 'Entry 1'
        self.mock_node.GetEntry.return_value = mock_entry
        (result,) = video_pyspin.get_string_value('TestNode', self.mock_camera)
        self.assertEqual('Entry 1', result)

    def test_get_string_value_exception(self):
        self.mock_camera.GetNodeMap.side_effect = Exception('Oh no!!')
        self.mock_node.__class__ = mock_pyspin.IInteger
        self.mock_node.GetValue.return_value = 42
        (result,) = video_pyspin.get_string_value('TestNode', self.mock_camera)
        self.assertEqual(result, '')


class TestGetValue(TestCase):
    def setUp(self):
        self.mock_camera = get_mock_camera()
        self.mock_node = self.mock_camera.TestNode

    def test_get_value(self):
        self.mock_node.__class__ = mock_pyspin.IInteger
        self.mock_node.GetValue.return_value = 42
        (result,) = video_pyspin.get_value('TestNode', self.mock_camera)
        self.assertEqual(42, result)

    def test_get_value_exception(self):
        self.mock_camera.GetNodeMap.side_effect = Exception('Oh no!!')
        self.mock_node.__class__ = mock_pyspin.IInteger
        self.mock_node.GetValue.return_value = 42
        (result,) = video_pyspin.get_value('TestNode', self.mock_camera)
        self.assertFalse(result)


class TestSetValueInt(TestCase):
    def setUp(self):
        self.mock_camera = get_mock_camera()
        self.mock_node = self.mock_camera.TestNode
        self.mock_node.__class__ = mock_pyspin.IInteger
        self.mock_node.GetValue.return_value = 100
        self.mock_node.GetMin.return_value = 50
        self.mock_node.GetMax.return_value = 150

    def test_set_value_integer_in_range_and_different(self):
        # Simulate an integer node
        (result,) = video_pyspin.set_value('TestNode', 120, self.mock_camera)
        self.mock_node.GetMin.assert_called_once()
        self.mock_node.GetMax.assert_called_once()
        self.mock_node.SetValue.assert_called_with(120)
        self.assertTrue(result)

    def test_set_value_integer_out_of_range(self):
        # The node’s value is out-of-range, so it should be clamped to the valid range.
        (result,) = video_pyspin.set_value('TestNode', 200, self.mock_camera)
        self.mock_node.SetValue.assert_called_with(150)
        self.assertTrue(result)

    def test_set_value_integer_already_set_value(self):
        # If the value already equals node.GetValue(), no SetValue call should be made.
        (result,) = video_pyspin.set_value('TestNode', 100, self.mock_camera)
        self.mock_node.SetValue.assert_not_called()
        self.assertTrue(result)


class TestSetValueFloat(TestCase):
    def setUp(self):
        self.mock_camera = get_mock_camera()
        self.mock_node = self.mock_camera.TestNode
        self.mock_node.__class__ = mock_pyspin.IFloat
        self.mock_node.GetValue.return_value = 1.5
        self.mock_node.GetMin.return_value = 0.0
        self.mock_node.GetMax.return_value = 5.0

    def test_set_value_float_in_range_and_different(self):
        # Simulate a float node.
        (result,) = video_pyspin.set_value('TestNode', 3.2, self.mock_camera)
        self.mock_node.GetMin.assert_called_once()
        self.mock_node.GetMax.assert_called_once()
        self.mock_node.SetValue.assert_called_with(3.2)
        self.assertTrue(result)


class TestSetValueBoolean(TestCase):
    def setUp(self):
        self.mock_camera = get_mock_camera()
        self.mock_node = self.mock_camera.TestNode
        self.mock_node.__class__ = mock_pyspin.IBoolean
        self.mock_node.GetValue.return_value = False

    def test_set_value_boolean_correct_type(self):
        (result,) = video_pyspin.set_value('TestNode', False, self.mock_camera)
        self.assertTrue(result)

    def test_set_value_boolean_incorrect_type(self):
        (result,) = video_pyspin.set_value('TestNode', 1, self.mock_camera)
        self.assertFalse(result)


class TestSetValueEnumeration(TestCase):
    def setUp(self):
        self.mock_camera = get_mock_camera()
        self.mock_node = self.mock_camera.TestNode
        self.mock_node.__class__ = mock_pyspin.IEnumeration
        self.mock_node.GetIntValue.return_value = 100
        entry1 = MagicMock()
        entry1.GetName.return_value = 'TestNode_Mono8'
        entry1.GetDisplayName.return_value = 'Mono8'
        entry2 = MagicMock()
        entry2.GetName.return_value = 'TestNode_Mono12'
        entry2.GetDisplayName.return_value = 'Mono12'
        self.mock_node.GetEntries.return_value = [entry1, entry2]

    def test_set_value_enumeration_integer(self):
        (result,) = video_pyspin.set_value('TestNode', 200, self.mock_camera)
        self.mock_node.SetValue.assert_called_with(200)
        self.assertTrue(result)

    def test_set_value_enumeration_string_valid(self):
        mock_pyspin.TestNode_Mono12 = 300
        (result,) = video_pyspin.set_value('TestNode', 'Mono12', self.mock_camera)
        self.mock_node.SetValue.assert_called_with(300)
        self.assertTrue(result)

    def test_set_value_enumeration_string_invalid(self):
        (result,) = video_pyspin.set_value('TestNode', 'InvalidEnum', self.mock_camera)
        self.assertFalse(result)


class TestSetValueUnsupportedNodeType(TestCase):
    def test_set_value_unsupported_node_type(self):
        mock_camera = get_mock_camera()
        mock_camera.TestNode.__class__ = None
        (result,) = video_pyspin.set_value('TestNode', 123, mock_camera)
        self.assertFalse(result)
