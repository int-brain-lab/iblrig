import sys
from unittest import TestCase
from unittest.mock import MagicMock, patch


class MockCameraPtr:
    pass


class MockCameraList:
    Clear = MagicMock()
    GetByIndex = MagicMock()
    GetBySerial = MagicMock()
    __len__ = MagicMock(return_value=1)
    __getitem__ = MagicMock()


class MockInstance(MagicMock):
    GetCameras = MagicMock(return_value=MockCameraList())


class MockNodeList(MagicMock):
    GetNode = MagicMock()


class MockIEnumeration:
    pass


class MockIInteger:
    pass


class MockIFloat:
    pass


class MockIBoolean:
    pass


def get_mock_pyspin():
    mock_pyspin = MagicMock()
    mock_pyspin.CameraPtr = MockCameraPtr
    mock_pyspin.CameraList = MockCameraList
    mock_pyspin.IEnumeration = MockIEnumeration
    mock_pyspin.IInteger = MockIInteger
    mock_pyspin.IFloat = MockIFloat
    mock_pyspin.IBoolean = MockIBoolean
    mock_pyspin.IsReadable.return_value = True
    mock_pyspin.IsWritable.return_value = True
    mock_pyspin.System.GetInstance.return_value = MockInstance()
    mock_pyspin.SpinnakerException = Exception
    return mock_pyspin


sys.modules['PySpin'] = MockPySpin = get_mock_pyspin()
from iblrig import video_pyspin  # noqa: E402


def get_mock_camera():
    mock_camera = MagicMock()
    mock_camera.__class__ = MockPySpin.CameraPtr
    mock_camera.DeviceID = MagicMock(return_value='123456789')
    mock_camera.DeviceModelName = MagicMock(return_value='MockCamera')
    mock_camera.TestNode.GetUnit.return_value = 'MockUnit'
    mock_camera.TestNode.GetDisplayName.return_value = 'MockDisplayName'
    mock_camera.GetNodeMap = MockNodeList()
    # mock_camera.GetNodeMap.GetNode = MagicMock(return_value=mock_camera.TestNode)
    mock_camera.IsInitialized = MagicMock(side_effect=[False, True])
    return mock_camera


class TestCameraInitialization(TestCase):
    @patch.object(MockPySpin.CameraList, '__len__', return_value=0)
    def test_initialization_no_cameras(self, mock_camera_list):
        """When no cameras are available, a ValueError should be raised."""
        with self.assertRaisesRegex(ValueError, 'No cameras'):
            video_pyspin.Camera()

    @patch.object(MockPySpin.CameraList, '__len__', return_value=1)
    @patch.object(MockPySpin.CameraList, '__getitem__', return_value=get_mock_camera())
    def test_initialization_one_camera_no_identifier(self, *_):
        """Successful (de)initialization with one camera and no identifier."""
        camera = video_pyspin.Camera()
        camera_ptr = camera._camera_ptr
        camera_ptr.Init.assert_called_once()
        self.assertIsInstance(camera_ptr, MockPySpin.CameraPtr)
        del camera
        camera_ptr.DeInit.assert_called_once()

    @patch.object(MockPySpin.CameraList, '__len__', return_value=1)
    @patch.object(MockPySpin.CameraList, '__getitem__', return_value=get_mock_camera())
    def test_initialization_context_manager(self, *_):
        """Successful (de)initialization with one camera and no identifier in context manager."""
        with video_pyspin.Camera() as camera:
            camera_ptr = camera._camera_ptr
            camera_ptr.Init.assert_called_once()
            self.assertIsInstance(camera_ptr, MockPySpin.CameraPtr)
        camera_ptr.DeInit.assert_called_once()

    @patch.object(MockPySpin.CameraList, '__len__', return_value=2)
    def test_initialization_multiple_cameras_no_identifier(self, *_):
        """When multiple cameras are available but no identifier is specified, a ValueError should be raised."""
        with self.assertRaisesRegex(ValueError, 'More than one camera'):
            video_pyspin.Camera()

    @patch.object(MockCameraList, 'GetByIndex', return_value=get_mock_camera())
    def test_initialization_by_index(self, _):
        """Successful initialization by index"""
        camera = video_pyspin.Camera(0)
        MockCameraList.GetByIndex.assert_called_once_with(0)
        camera._camera_ptr.Init.assert_called_once()

    @patch.object(MockCameraList, 'GetByIndex', side_effect=MockPySpin.SpinnakerException)
    def test_initialization_by_index_invalid(self, _):
        """Failed initialization by index"""
        with self.assertRaisesRegex(ValueError, 'No camera with index 5'):
            video_pyspin.Camera(5)

    @patch.object(MockCameraList, 'GetBySerial', return_value=get_mock_camera())
    def test_initialization_by_serial(self, _):
        """Successful initialization by serial number"""
        camera = video_pyspin.Camera('123456789')
        MockCameraList.GetBySerial.assert_called_once_with('123456789')
        camera._camera_ptr.Init.assert_called_once()

    @patch.object(MockCameraList, 'GetBySerial', return_value=get_mock_camera())
    def test_initialization_by_serial_invalid(self, mock_get_by_serial):
        """Failed initialization by serial number"""
        mock_camera_ptr = mock_get_by_serial.return_value
        with (
            patch.object(mock_camera_ptr, 'IsValid', return_value=False),
            self.assertRaisesRegex(ValueError, 'No camera with serial'),
        ):
            video_pyspin.Camera('invalid')


class TestCameraGetNode(TestCase):
    def setUp(self, *_):
        with patch.object(MockCameraList, 'GetByIndex', return_value=get_mock_camera()):
            self.mock_camera = video_pyspin.Camera(0)
        self.mock_node = self.mock_camera._camera_ptr.TestNode

    def test_get_node(self):
        node = self.mock_camera._get_node('TestNode')
        self.assertIs(self.mock_node, node)
        with (
            patch.object(MockNodeList, 'GetNode', return_value=None),
            self.assertRaisesRegex(AttributeError, 'No such node'),
        ):
            self.mock_camera._get_node('NonExistentNode')

    def test_get_readable_node(self):
        node = self.mock_camera._get_readable_node('TestNode')
        self.assertIs(self.mock_node, node)
        MockPySpin.IsReadable.return_value = False
        with self.assertRaisesRegex(AttributeError, 'is not readable'):
            self.mock_camera._get_readable_node('TestNode')
        MockPySpin.IsReadable.return_value = True
        delattr(self.mock_node, 'GetValue')
        with self.assertRaisesRegex(AttributeError, 'has no .*? attribute'):
            self.mock_camera._get_readable_node('TestNode')

    def test_get_writable_node(self):
        node = self.mock_camera._get_writable_node('TestNode')
        self.assertIs(self.mock_node, node)
        MockPySpin.IsWritable.return_value = False
        with self.assertRaisesRegex(AttributeError, 'is not writable'):
            self.mock_camera._get_writable_node('TestNode')
        MockPySpin.IsWritable.return_value = True
        delattr(self.mock_node, 'SetValue')
        with self.assertRaisesRegex(AttributeError, 'has no .*? attribute'):
            self.mock_camera._get_writable_node('TestNode')


class TestCameraGetValue(TestCase):
    def setUp(self):
        with patch.object(MockCameraList, 'GetByIndex', return_value=get_mock_camera()):
            self.mock_camera = video_pyspin.Camera(0)
        self.mock_node = self.mock_camera._camera_ptr.TestNode

    def test_get_value(self):
        self.mock_node.__class__ = MockPySpin.IInteger
        self.mock_node.GetValue.return_value = 42
        result = self.mock_camera.get_value('TestNode')
        self.assertEqual(42, result)

    def test_get_value_exception(self):
        self.mock_camera._camera_ptr.GetNodeMap.side_effect = Exception('Oh no!!')
        self.mock_node.__class__ = MockPySpin.IInteger
        self.mock_node.GetValue.return_value = 42
        result = self.mock_camera.get_value('TestNode')
        self.assertIsNone(result)


class TestCameraGetStringValue(TestCase):
    def setUp(self):
        with patch.object(MockCameraList, 'GetByIndex', return_value=get_mock_camera()):
            self.mock_camera = video_pyspin.Camera(0)
        self.mock_node = self.mock_camera._camera_ptr.TestNode

    def test_get_formatted_value_integer_node(self):
        self.mock_node.__class__ = MockPySpin.IInteger
        self.mock_node.GetValue.return_value = 42
        result = self.mock_camera.get_formatted_value('TestNode')
        self.assertEqual('42 MockUnit', result)

    def test_get_formatted_value_enumeration_node(self):
        self.mock_node.__class__ = MockPySpin.IEnumeration
        mock_entry = MagicMock()
        mock_entry.GetDisplayName.return_value = 'Entry 1'
        self.mock_node.GetEntry.return_value = mock_entry
        result = self.mock_camera.get_formatted_value('TestNode')
        self.assertEqual('Entry 1', result)

    def test_get_formatted_value_exception(self):
        self.mock_camera._camera_ptr.GetNodeMap.side_effect = Exception('Oh no!!')
        self.mock_node.__class__ = MockPySpin.IInteger
        self.mock_node.GetValue.return_value = 42
        result = self.mock_camera.get_formatted_value('TestNode')
        self.assertEqual(result, '')


class TestCameraSetValueInt(TestCase):
    def setUp(self):
        with patch.object(MockCameraList, 'GetByIndex', return_value=get_mock_camera()):
            self.mock_camera = video_pyspin.Camera(0)
        self.mock_node = self.mock_camera._camera_ptr.TestNode
        self.mock_node.__class__ = MockPySpin.IInteger
        self.mock_node.GetValue.return_value = 100
        self.mock_node.GetMin.return_value = 50
        self.mock_node.GetMax.return_value = 150

    def test_set_value_integer_in_range_and_different(self):
        # Simulate an integer node
        result = self.mock_camera.set_value('TestNode', 120)
        self.mock_node.GetMin.assert_called_once()
        self.mock_node.GetMax.assert_called_once()
        self.mock_node.SetValue.assert_called_with(120)
        self.assertTrue(result)

    def test_set_value_integer_out_of_range(self):
        # The node’s value is out-of-range, so it should be clamped to the valid range.
        result = self.mock_camera.set_value('TestNode', 200)
        self.mock_node.SetValue.assert_called_with(150)
        self.assertTrue(result)

    def test_set_value_integer_already_set_value(self):
        # If the value already equals node.GetValue(), no SetValue call should be made.
        result = self.mock_camera.set_value('TestNode', 100)
        self.mock_node.SetValue.assert_not_called()
        self.assertTrue(result)


class TestCameraSetValueFloat(TestCase):
    def setUp(self):
        with patch.object(MockCameraList, 'GetByIndex', return_value=get_mock_camera()):
            self.mock_camera = video_pyspin.Camera(0)
        self.mock_node = self.mock_camera._camera_ptr.TestNode
        self.mock_node.__class__ = MockPySpin.IFloat
        self.mock_node.GetValue.return_value = 1.5
        self.mock_node.GetMin.return_value = 0.0
        self.mock_node.GetMax.return_value = 5.0

    def test_set_value_float_in_range_and_different(self):
        # Simulate a float node.
        result = self.mock_camera.set_value('TestNode', 3.2)
        self.mock_node.GetMin.assert_called_once()
        self.mock_node.GetMax.assert_called_once()
        self.mock_node.SetValue.assert_called_with(3.2)
        self.assertTrue(result)


class TestCameraSetValueBoolean(TestCase):
    def setUp(self):
        with patch.object(MockCameraList, 'GetByIndex', return_value=get_mock_camera()):
            self.mock_camera = video_pyspin.Camera(0)
        self.mock_node = self.mock_camera._camera_ptr.TestNode
        self.mock_node.__class__ = MockPySpin.IBoolean
        self.mock_node.GetValue.return_value = False

    def test_set_value_boolean_correct_type(self):
        result = self.mock_camera.set_value('TestNode', False)
        self.assertTrue(result)

    def test_set_value_boolean_incorrect_type(self):
        result = self.mock_camera.set_value('TestNode', 1)
        self.assertFalse(result)


class TestCameraSetValueEnumeration(TestCase):
    def setUp(self):
        with patch.object(MockCameraList, 'GetByIndex', return_value=get_mock_camera()):
            self.mock_camera = video_pyspin.Camera(0)
        self.mock_node = self.mock_camera._camera_ptr.TestNode
        self.mock_node.__class__ = MockPySpin.IEnumeration
        self.mock_node.GetIntValue.return_value = 100
        entry1 = MagicMock()
        entry1.GetName.return_value = 'TestNode_Mono8'
        entry1.GetDisplayName.return_value = 'Mono8'
        entry2 = MagicMock()
        entry2.GetName.return_value = 'TestNode_Mono12'
        entry2.GetDisplayName.return_value = 'Mono12'
        self.mock_node.GetEntries.return_value = [entry1, entry2]

    def test_set_value_enumeration_integer(self):
        result = self.mock_camera.set_value('TestNode', 200)
        self.mock_node.SetValue.assert_called_with(200)
        self.assertTrue(result)

    def test_set_value_enumeration_string_valid(self):
        MockPySpin.TestNode_Mono12 = 300
        result = self.mock_camera.set_value('TestNode', 'Mono12')
        self.mock_node.SetValue.assert_called_with(300)
        self.assertTrue(result)

    def test_set_value_enumeration_string_invalid(self):
        del MockPySpin.TestNode_InvalidEnum
        result = self.mock_camera.set_value('TestNode', 'InvalidEnum')
        self.assertFalse(result)


class TestCameraSetValueUnsupportedNodeType(TestCase):
    def test_set_value_unsupported_node_type(self):
        with patch.object(MockCameraList, 'GetByIndex', return_value=get_mock_camera()):
            mock_camera = video_pyspin.Camera(0)
        mock_camera._camera_ptr.TestNode.__class__ = None
        result = mock_camera.set_value('TestNode', 123)
        self.assertFalse(result)
