import logging
import time
import warnings
from typing import Any

import PySpin
from pydantic import NonNegativeInt, validate_call

from iblrig.pydantic_definitions import HardwareSettingsCameraParameters

logger = logging.getLogger(__name__)

NODE_MAPPING = {
    PySpin.intfIValue: PySpin.CValuePtr,
    PySpin.intfIBase: PySpin.CBasePtr,
    PySpin.intfIInteger: PySpin.CIntegerPtr,
    PySpin.intfIBoolean: PySpin.CBooleanPtr,
    PySpin.intfICommand: PySpin.CCommandPtr,
    PySpin.intfIFloat: PySpin.CFloatPtr,
    PySpin.intfIString: PySpin.CStringPtr,
    PySpin.intfIRegister: PySpin.CRegisterPtr,
    PySpin.intfICategory: PySpin.CCategoryPtr,
    PySpin.intfIEnumeration: PySpin.CEnumerationPtr,
    PySpin.intfIEnumEntry: PySpin.CEnumEntryPtr,
}


def camera_log(level: int, camera: PySpin.CameraPtr, message: str, stacklevel: int = 2) -> bool:
    """
    Log a message related to a camera.

    Parameters
    ----------
    level : int
        The logging level.
    camera : PySpin.CameraPtr
        A pointer to the camera object from the PySpin library.
    message : str
        The message to log, which will be associated with the camera.
    stacklevel : int, optional
        The stack level to use for the logging call (default is 2).

    Returns
    -------
    bool
        Returns True if the logging level is less than ERROR, otherwise False.
    """
    logger.log(level=level, msg=f'Camera #{camera.DeviceID()}: {message.strip(" .")}.', stacklevel=stacklevel)
    return level < logging.ERROR


class Camera:
    """A class to manage a camera instance using the PySpin library."""

    _serial_number: str
    _model_name: str
    _label: str = ''
    _index: int
    _settings: HardwareSettingsCameraParameters

    @validate_call()
    def __init__(self, identifier: str | NonNegativeInt | HardwareSettingsCameraParameters | None = None):
        """Initializes the Camera instance.

        Parameters
        ----------
        identifier : str or int, optional
            Index or serial number of the camera.
            If not provided and only one camera is available, this camera will be used.
        init_cameras : bool, optional
            If True, initializes the cameras upon creation of the instance (default is True).
        """
        self._instance = PySpin.System.GetInstance()
        self._camera_list = self._instance.GetCameras()
        if isinstance(identifier, HardwareSettingsCameraParameters):
            self._settings = identifier
            self._label = identifier.LABEL.upper()
            identifier = getattr(identifier, 'SERIAL', identifier.INDEX)
        if isinstance(identifier, int):
            try:
                self._camera_ptr = self._camera_list.GetByIndex(identifier)
            except (PySpin.SpinnakerException, OverflowError) as e:
                raise ValueError(f'No camera with index {identifier}') from e
        elif isinstance(identifier, str):
            self._camera_ptr = self._camera_list.GetBySerial(identifier)
            if not self._camera_ptr.IsValid():
                raise ValueError(f"No camera with serial '{identifier}'")
        elif identifier is None:
            if len(self._camera_list) == 0:
                raise ValueError('No cameras available')
            elif len(self._camera_list) == 1:
                self._camera_ptr = self._camera_list[0]
            elif len(self._camera_list) > 1:
                raise ValueError('More than one camera available. Please specify by index or serial.')
        for idx, ptr in enumerate(self._camera_list):
            if ptr == self._camera_ptr:
                self._index = idx

        self._initialize()

    def __enter__(self) -> PySpin.CameraList:
        """Enters the runtime context related to this object.

        Returns
        -------
        Camera
            The current instance.
        """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Exits the runtime context related to this object."""
        self._release()

    def __del__(self):
        """Destructor."""
        self._release()

    def _release(self):
        if hasattr(self, '_camera_list'):
            self._camera_list.Clear()
            delattr(self, '_camera_list')
        if hasattr(self, '_camera_ptr'):
            self._deinitialize()
            delattr(self, '_camera_ptr')
        self._instance.ReleaseInstance()

    def _initialize(self):
        if not self._camera_ptr.IsInitialized():
            self._camera_ptr.Init()
            self._serial_number = self._camera_ptr.DeviceSerialNumber()
            self._model_name = self._camera_ptr.DeviceModelName()
            self._log(logging.INFO, f'Initializing {self._model_name} (Index {self._index}, SN {self._serial_number})')

    def _deinitialize(self):
        if self._camera_ptr.IsInitialized():
            self._log(logging.INFO, f'Deinitializing {self._model_name} (Index {self._index}, SN {self._serial_number})')
            self._camera_ptr.DeInit()

    def _cast_node(self, node: PySpin.INode) -> Any:
        interface_type = node.GetPrincipalInterfaceType()
        caster = NODE_MAPPING.get(interface_type)
        if caster is None:
            raise TypeError(f'Unknown node interface type: {interface_type}')
        return caster(node)

    def _get_node(self, node_name: str) -> PySpin.INode:
        node_map = self._camera_ptr.GetNodeMap()
        node = node_map.GetNode(node_name)
        if node is None:
            raise AttributeError(f'No such node: {node_name}')
        return self._cast_node(node)

    def _get_writable_node(self, node_name: str) -> PySpin.INode:
        node = self._get_node(node_name)
        if not PySpin.IsWritable(node):
            raise AttributeError(f'{node.GetDisplayName()} is not writable')
        return node

    def _get_readable_node(self, node_name: str) -> PySpin.INode:
        node = self._get_node(node_name)
        if not PySpin.IsReadable(node):
            raise AttributeError(f'{node.GetDisplayName()} is not readable')
        return node

    def _log(self, level: int, message: str, stacklevel: int = 2) -> bool:
        logger.log(
            level=level,
            msg=f'Camera {self._index if len(self._label) == 0 else self._label}: {message.strip(" .")}.',
            stacklevel=stacklevel,
        )
        return level < logging.ERROR

    def get_value(self, node_name: str) -> Any | None:
        """
        Get the value of a camera node.

        Parameters
        ----------
        node_name : str
            The name of the node to get the value of.

        Returns
        -------
        Any
            The value of the node.
        None
            If there was an error reading the node.
        """
        try:
            node = self._get_readable_node(node_name)
            return node.GetValue()
        except Exception as e:
            self._log(logging.ERROR, f'Error getting value: {e.args[0]}')
            return None

    def get_formatted_value(self, node_name: str) -> str:
        """
        Get the value of a camera node, formatted as a string.

        Parameters
        ----------
        node_name : str
            The name of the node to get the value of.

        Returns
        -------
        str
            The value of the node, formatted as a string.
        """
        try:
            node = self._get_readable_node(node_name)
            if isinstance(node, PySpin.IEnumeration):
                return node.GetEntry(node.GetIntValue()).GetDisplayName()
            else:
                return f'{node.GetValue():g}{" " + node.GetUnit() if hasattr(node, "GetUnit") else ""}'
        except Exception as e:
            self._log(logging.ERROR, f'Error getting value: {e.args[0]}')
            return ''

    def set_value(self, node_name: str, value: Any) -> bool:
        """
        Set the value of a camera node to a specified value.

        Parameters
        ----------
        node_name : str
            The name of the node to set the value for.
        value : Any
            The value to set for the specified node. The type of value must match the node's expected type.
            The routine will be skipped if value is None.

        Returns
        -------
        bool
            True if the property was set successfully, False otherwise.
        """
        if value is None:
            return True
        try:
            # get node
            node = self._get_writable_node(node_name)
            disp_name = node.GetDisplayName()

            # assert types
            val_type = type(value)
            if isinstance(node, PySpin.CIntegerPtr):
                expected_value_types = [int]
            elif isinstance(node, PySpin.CFloatPtr):
                expected_value_types = [int, float]
            elif isinstance(node, PySpin.CBooleanPtr):
                expected_value_types = [bool]
            elif isinstance(node, PySpin.CEnumerationPtr):
                expected_value_types = [int, str]
                if val_type is str:
                    entries = [self._cast_node(entry) for entry in node.GetEntries()]
                    valid = {entry.GetSymbolic(): entry.GetValue() for entry in entries}
                    if value in valid:
                        value = valid[value]
                        val_type = type(value)
                    else:
                        expected_val_str = ', '.join(valid.keys())
                        expected_val_str = ' or'.join(expected_val_str.rsplit(',', 1))
                        raise ValueError(f'String value for {disp_name} must be {expected_val_str}')
            else:
                raise TypeError(f'Unsupported node type: {type(node).__name__}')
            if val_type not in expected_value_types:
                expected_val_type_str = ', '.join([f'{x.__name__}' for x in expected_value_types])
                expected_val_type_str = ' or'.join(expected_val_type_str.rsplit(',', 1))
                raise TypeError(f'Value for {disp_name} must be of type {expected_val_type_str} - not {val_type.__name__}')

            # limit value to valid range
            if isinstance(node, (PySpin.IInteger, PySpin.IFloat)) and not (node.GetMin() <= value <= node.GetMax()):  # noqa: UP038
                value = min(max(value, node.GetMin()), node.GetMax())

            # set value (if necessary)
            if isinstance(node, PySpin.CEnumerationPtr) and value != node.GetIntValue():
                value_str = node.GetEntry(value).GetDisplayName()
                node.SetIntValue(value)
            elif not isinstance(node, PySpin.CEnumerationPtr) and value != node.GetValue():
                value_str = f'{value:g}{(" " + node.GetUnit()) if hasattr(node, "GetUnit") else ""}'
                node.SetValue(value)
            else:
                return True
            return self._log(logging.INFO, f'Setting {disp_name} to {value_str}')
        except Exception as e:
            return self._log(logging.ERROR, f'Error setting value: {e.args[0]}')

    def reset(self):
        """Reset camera and wait for it to come back online."""
        try:
            self._camera_ptr.DeviceReset()
        except PySpin.SpinnakerException as e:
            self._log(logging.ERROR, f'Error resetting camera: {e}')
        else:
            self._log(logging.INFO, 'Resetting camera')
        finally:
            self._deinitialize()
        self._log(logging.INFO, 'Waiting for camera to come back online (~10 s)')
        online = False
        while not online:
            online = True
            try:
                self._initialize()
            except PySpin.SpinnakerException:
                online = False
                time.sleep(0.2)
            else:
                self._log(logging.INFO, 'Camera is back online')

    def apply_settings(self, settings: HardwareSettingsCameraParameters):
        # Make sure we're dealing with the correct camera
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            if (self._serial_number != settings.SERIAL) and (self._index == settings.INDEX):
                raise ValueError('Supplied settings are intended for a camera with different index or serial number.')

        # Disable trigger mode
        self.set_value(node_name='TriggerMode', value=0)

        # set analog parameters
        self.set_value('BlackLevel', settings.BLACK_LEVEL)
        self.set_value('GainAuto', 'Off')
        self.set_value('Gain', settings.GAIN_DB)

        # Set video mode and frame dimensions
        self.set_value('VideoMode', settings.VIDEO_MODE)
        if settings.WIDTH is not None:
            self.set_value('Width', settings.WIDTH)
        if settings.HEIGHT is not None:
            self.set_value('Height', settings.HEIGHT)

        # Set frame rate
        if settings.FPS is not None:
            self.set_value('AcquisitionFrameRateAuto', 'Off')
            self.set_value('AcquisitionFrameRate', settings.FPS)

        # Set exposure
        self.set_value('ExposureMode', 'Timed')
        self.set_value('ExposureAuto', 'Off')
        self.set_value('ExposureTime', settings.EXPOSURE_TIME_US)
        self.set_value('pgrExposureCompensationAuto', 'Off')
        self.set_value('pgrExposureCompensation', settings.EXPOSURE_COMPENSATION_EV)

        # Set GPIO
        for line in range(4):
            self.set_value('LineSelector', line)
            self.set_value('LineMode', settings.LINE_MODE[line])
            self.set_value('LineSource', settings.LINE_SOURCE[line])
            self.set_value('StrobeDuration', settings.STROBE_DURATION_US[line])
            self.set_value('StrobeDelay', settings.STROBE_DELAY_US[line])


class Cameras:
    """A class to manage camera instances using the PySpin library.

    This class provides a context manager for initializing and deinitializing cameras. It ensures that cameras are
    properly initialized when entering the context and deinitialized when exiting.
    """

    _instance = None

    @validate_call()
    def __init__(self, identifier: list[str | NonNegativeInt] | None = None, init_cameras: bool = True):
        """Initializes the Cameras instance.

        Parameters
        ----------
        init_cameras : bool, optional
            If True, initializes the cameras upon creation of the instance (default is True).
        """
        self._instance = PySpin.System.GetInstance()
        self._cameras = self._instance.GetCameras()

        if isinstance(identifier, list):
            device_ids = [i for i in identifier if isinstance(i, str)]
            indices = [i for i in identifier if isinstance(i, int)]
            for idx in range(len(self._cameras)):
                self._cameras[idx].Init()
                if not (self._cameras[idx].DeviceID() in device_ids or idx in indices):
                    self._cameras.RemoveByIndex(idx)
                self._cameras[idx].DeInit()

        self._init_cameras = init_cameras
        if init_cameras:
            for i in range(len(self._cameras)):
                self._cameras[i].Init()

    def __enter__(self) -> PySpin.CameraList:
        """Enters the runtime context related to this object.

        Returns
        -------
        PySpin.CameraList
            The list of initialized cameras.
        """
        return self._cameras

    def __exit__(self, exc_type, exc_value, traceback):
        """Exits the runtime context related to this object.

        Deinitializes the cameras if they were initialized and releases the system instance.
        """
        if self._init_cameras:
            for i in range(len(self._cameras)):
                self._cameras[i].DeInit()
        self._cameras.Clear()
        del self._cameras
        self._instance.ReleaseInstance()


def acquisition_ok() -> bool:
    """Test image acquisition for all available cameras.

    This function attempts to acquire an image from each camera and checks if the acquisition was successful. It logs
    the results of the acquisition test for each camera.

    Returns
    -------
    bool
        True if all cameras successfully acquired an image, False otherwise.
    """
    success = True
    with Cameras() as cameras:
        for i in range(len(cameras)):
            camera_log(logging.DEBUG, cameras[i], 'Testing image acquisition')
            try:
                cameras[i].BeginAcquisition()
                image = cameras[i].GetNextImage(1000)
                if image.IsValid() and image.GetImageStatus() == PySpin.SPINNAKER_IMAGE_STATUS_NO_ERROR:
                    camera_log(logging.INFO, cameras[i], 'Acquisition test was successful')
                else:
                    success = camera_log(logging.ERROR, cameras[i], 'Acquisition test failed')
            except Exception as e:
                success = camera_log(logging.ERROR, cameras[i], f'Acquisition test failed: {e.args[0]}')
            else:
                if image.IsValid():
                    image.Release()
            finally:
                cameras[i].EndAcquisition()
    return success


def reset_all_cameras():
    """Reset all available cameras and wait for them to come back online.

    This function initializes each camera, attempts to reset it, and then deinitializes it.
    After resetting, it waits for all cameras to come back online, logging the status of each camera.
    """
    with Cameras(init_cameras=False) as cameras:
        if len(cameras) == 0:
            return

        # Iterate through each camera and reset
        for i in range(len(cameras)):
            cameras[i].Init()
            try:
                cameras[i].DeviceReset()
            except PySpin.SpinnakerException as e:
                camera_log(logging.ERROR, cameras[i], f'Error resetting camera: {e}')
            else:
                camera_log(logging.INFO, cameras[i], 'Resetting camera')
            finally:
                cameras[i].DeInit()

        # Wait for all cameras to come back online
        for i in range(len(cameras)):
            camera_log(logging.INFO, cameras[i], 'Waiting for camera to come back online (~10 s)')
        all_cameras_online = False
        while not all_cameras_online:
            all_cameras_online = True
            for i in range(len(cameras)):
                try:
                    cameras[i].Init()
                except PySpin.SpinnakerException:
                    all_cameras_online = False
                else:
                    camera_log(logging.INFO, cameras[i], 'Camera is back online')
                    cameras[i].DeInit()
            if not all_cameras_online:
                time.sleep(0.2)


# @process_camera
# def enable_camera_trigger(enable: bool, camera: PySpin.CameraPtr) -> bool:
#     """Enable or disable the trigger for a specified camera or all cameras.
#
#     This function allows you to enable or disable the trigger mode for a given camera / given cameras.
#     If no camera is specified, it will enable or disable the trigger mode for all available cameras.
#
#     Parameters
#     ----------
#     enable : bool
#         A flag indicating whether to enable (True) or disable (False) the camera trigger.
#     camera : PySpin.CameraPtr, PySpin.CameraList or None, optional
#         A pointer to a specific camera instance, a list of instances, or None. If None is specified, all available
#         cameras will be considered.
#
#     Raises
#     ------
#     PySpin.SpinnakerException
#         If there is an error while setting the trigger mode for the camera.
#     """
#     return set_value(node_name='TriggerMode', value=int(enable), camera=camera)
#
#
# @process_camera
# def select_line(line: int | str, camera: PySpin.CameraPtr) -> bool:
#     return set_value(node_name='LineSelector', value=line, camera=camera)
#
#
# @process_camera
# def set_line_mode(value: int | str, camera: PySpin.CameraPtr) -> bool:
#     return set_value(node_name='LineMode', value=value, camera=camera)
#
#
# @process_camera
# def set_line_source(value: int | str, camera: PySpin.CameraPtr) -> bool:
#     return set_value(node_name='LineSource', value=value, camera=camera)
#
#
# @process_camera
# def set_framerate(value: float, camera: PySpin.CameraPtr) -> bool:
#     return set_value(node_name='AcquisitionFrameRate', value=value, camera=camera)
