import sys
from unittest import TestCase
from unittest.mock import MagicMock


class MockCameraPtr:
    pass


class MockIEnumeration:
    pass


class MockIInteger:
    pass


# Mock the PySpin module in sys.modules
mock_pyspin = MagicMock()
mock_pyspin.CameraPtr = MockCameraPtr
mock_pyspin.IsReadable.return_value = True
mock_pyspin.IsWritable.return_value = True
mock_pyspin.IEnumeration = MockIEnumeration
mock_pyspin.IInteger = MockIInteger
sys.modules['PySpin'] = mock_pyspin
from iblrig import video_pyspin  # noqa: E402


def get_mock_camera():
    mock_camera = MagicMock(spec=mock_pyspin.CameraPtr)
    mock_camera.DeviceID = MagicMock(return_value='123456789')
    mock_camera.TestNode = MagicMock()
    mock_camera.GetNodeMap = MagicMock()
    mock_camera.GetNodeMap.GetNode = MagicMock(return_value=mock_camera.TestNode)
    return mock_camera


class TestPrivateMethods(TestCase):
    def setUp(self):
        self.mock_camera = get_mock_camera()

    def test_get_node(self):
        node = video_pyspin._get_node('TestNode', self.mock_camera)
        self.assertIs(self.mock_camera.TestNode, node)
        with self.assertRaises(AttributeError):
            node = video_pyspin._get_node('NonExistentNode', self.mock_camera)

    def test_get_readable_node(self):
        node = video_pyspin._get_readable_node('TestNode', self.mock_camera)
        self.assertIs(self.mock_camera.TestNode, node)
        mock_pyspin.IsReadable.return_value = False
        with self.assertRaises(AttributeError):
            video_pyspin._get_readable_node('TestNode', self.mock_camera)
        mock_pyspin.IsReadable.return_value = True
        delattr(self.mock_camera.TestNode, 'GetValue')
        with self.assertRaises(AttributeError):
            video_pyspin._get_readable_node('TestNode', self.mock_camera)

    def test_get_writable_node(self):
        node = video_pyspin._get_writable_node('TestNode', self.mock_camera)
        self.assertIs(self.mock_camera.TestNode, node)
        mock_pyspin.IsWritable.return_value = False
        with self.assertRaises(AttributeError):
            video_pyspin._get_writable_node('TestNode', self.mock_camera)
        mock_pyspin.IsWritable.return_value = True
        delattr(self.mock_camera.TestNode, 'SetValue')
        with self.assertRaises(AttributeError):
            video_pyspin._get_writable_node('TestNode', self.mock_camera)


class TestGetStringValue(TestCase):
    def setUp(self):
        self.mock_camera = get_mock_camera()

    def test_get_string_value_integer_node(self):
        self.mock_camera.TestNode.__class__ = mock_pyspin.IInteger
        self.mock_camera.TestNode.GetValue.return_value = 42
        self.mock_camera.TestNode.GetUnit.return_value = 'TestUnits'
        (result,) = video_pyspin.get_string_value('TestNode', self.mock_camera)
        self.assertEqual('42 TestUnits', result)

    def test_get_string_value_enumeration_node(self):
        self.mock_camera.TestNode.__class__ = mock_pyspin.IEnumeration
        mock_entry = MagicMock()
        mock_entry.GetDisplayName.return_value = 'Entry 1'
        self.mock_camera.TestNode.GetEntry.return_value = mock_entry
        (result,) = video_pyspin.get_string_value('TestNode', self.mock_camera)
        self.assertEqual('Entry 1', result)

    def test_get_string_value_exception(self):
        self.mock_camera.GetNodeMap.side_effect = Exception('Oh no!!')
        self.mock_camera.TestNode.__class__ = mock_pyspin.IInteger
        self.mock_camera.TestNode.GetValue.return_value = 42
        self.mock_camera.TestNode.GetUnit.return_value = 'TestUnits'
        (result,) = video_pyspin.get_string_value('TestNode', self.mock_camera)
        self.assertEqual(result, '')


class TestGetValue(TestCase):
    def setUp(self):
        self.mock_camera = get_mock_camera()

    def test_get_value(self):
        self.mock_camera.TestNode.__class__ = mock_pyspin.IInteger
        self.mock_camera.TestNode.GetValue.return_value = 42
        (result,) = video_pyspin.get_value('TestNode', self.mock_camera)
        self.assertEqual(42, result)

    def test_get_value_exception(self):
        self.mock_camera.GetNodeMap.side_effect = Exception('Oh no!!')
        self.mock_camera.TestNode.__class__ = mock_pyspin.IInteger
        self.mock_camera.TestNode.GetValue.return_value = 42
        (result,) = video_pyspin.get_value('TestNode', self.mock_camera)
        self.assertEqual(result, False)
