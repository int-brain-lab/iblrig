import functools
import logging
import time
from collections.abc import Callable
from typing import Any

import PySpin

logger = logging.getLogger(__name__)


def camera_log(level: int, camera: PySpin.CameraPtr, message: str, stacklevel: int = 2) -> bool:
    """
    Log a message related to a camera.

    Parameters
    ----------
    level : int
        The logging level (e.g., DEBUG, INFO, WARNING, ERROR, CRITICAL).
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


class Cameras:
    """A class to manage camera instances using the PySpin library.

    This class provides a context manager for initializing and deinitializing cameras. It ensures that cameras are
    properly initialized when entering the context and deinitialized when exiting.
    """

    _instance = None

    def __init__(self, init_cameras: bool = True):
        """Initializes the Cameras instance.

        Parameters
        ----------
        init_cameras : bool, optional
            If True, initializes the cameras upon creation of the instance (default is True).
        """
        self._instance = PySpin.System.GetInstance()
        self._cameras = self._instance.GetCameras()
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
        self._instance.ReleaseInstance()


def process_camera(func: Callable[..., Any]) -> Callable[..., tuple[Any, ...]]:
    """Decorator to process a camera or a list of cameras.

    This decorator allows a function to accept a single camera instance, a list of camera instances, or None. If None
    is provided, the decorator will iterate over all available cameras managed by the Cameras context manager and call
    the decorated function for each camera.

    Parameters
    ----------
    func : Callable
        The function to be decorated, which will be called with each camera instance.

    Returns
    -------
    Callable
        The wrapped function that processes the camera input.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> tuple[Any, ...]:
        # find camera parameter
        if 'camera' in kwargs:
            camera = kwargs.pop('camera')
        elif len(args) > 0 and isinstance(args[-1], PySpin.CameraPtr | PySpin.CameraList):
            camera = args[-1]
            args = args[:-1]
        else:
            camera = None

        # call the wrapped function
        results = []
        if isinstance(camera, PySpin.CameraPtr):
            results.append(func(*args, camera=camera, **kwargs))
        elif isinstance(camera, PySpin.CameraList):
            for i in range(len(camera)):
                results.append(func(*args, camera=camera[i], **kwargs))
        if camera is None:
            with Cameras() as camera_list:
                for i in range(len(camera_list)):
                    results.append(func(*args, camera=camera_list[i], **kwargs))

        # return results as tuple
        return tuple(results)

    return wrapper  # type: ignore


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
                    camera_log(logging.ERROR, cameras[i], 'Acquisition test failed')
                    success = False
            except Exception as e:
                camera_log(logging.ERROR, cameras[i], f'Acquisition test failed: {e.args[0]}')
                success = False
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


@process_camera
def set_value(node_name: str, value: Any, camera: PySpin.CameraPtr) -> bool:
    """
    Set the value of a camera node to a specified value.

    Parameters
    ----------
    node_name : str
        The name of the node to set the value for.
    value : Any
        The value to set for the specified node. The type of value must match the node's expected type.
    camera : PySpin.CameraPtr, PySpin.CameraList or None, optional
        A pointer to a specific camera instance, a list of instances, or None. If None is specified, all available
        cameras will be considered.

    Returns
    -------
    bool
        True if the property was set successfully, False otherwise.
    """
    try:
        # get node
        assert hasattr(camera, node_name), f"No such node: '{node_name}'"
        node = getattr(camera, node_name)
        assert hasattr(node, 'SetValue'), f'node '{node_name}' has no SetValue() attribute'
        disp_name = node.GetDisplayName()
        assert PySpin.IsWritable(node), f'{disp_name} is not writable'

        # assert types
        node_type = type(node)
        val_type = type(value)
        match node_type:
            case PySpin.IInteger:
                expected_value_types = [int]
            case PySpin.IFloat:
                expected_value_types = [int, float]
            case PySpin.IBoolean:
                expected_value_types = [bool]
            case _ if isinstance(node, PySpin.IEnumeration):
                expected_value_types = [int, str]
                if val_type is str:
                    if hasattr(PySpin, enumeration_name := f'{node_name}_{value}'):
                        value = getattr(PySpin, enumeration_name)
                        val_type = type(value)
                    else:
                        expected_val_str = ', '.join([f"'{n.GetName().rsplit('_', 1)[-1]}'" for n in node.GetEntries()])
                        expected_val_str = ' or'.join(expected_val_str.rsplit(',', 1))
                        raise ValueError(f'String value for {disp_name} must be {expected_val_str}')
            case _:
                raise TypeError(f'Unsupported node type: {node_type.__name__}')
        if val_type not in expected_value_types:
            expected_val_type_str = ', '.join([f'{x.__name__}' for x in expected_value_types])
            expected_val_type_str = ' or'.join(expected_val_type_str.rsplit(',', 1))
            raise TypeError(f'Value for {disp_name} must be of type {expected_val_type_str} - not {val_type.__name__}')

        # limit value to valid range
        if node_type in (PySpin.IInteger, PySpin.IFloat) and not node.GetMin() <= value <= node.GetMax():
            value = min(max(value, node.GetMin()), node.GetMax())

        # set value (if necessary)
        if isinstance(node, PySpin.IEnumeration) and value != node.GetIntValue():
            value_str = node.GetEntry(value).GetDisplayName()
        elif value != node.GetValue():
            value_str = f'{value:g}{" " + node.GetUnit() if hasattr(node, "GetUnit") else ""}'
        else:
            return True
        node.SetValue(value)
        return camera_log(logging.INFO, camera, f'Setting {disp_name} to {value_str}')
    except Exception as e:
        return camera_log(logging.ERROR, camera, f"Error setting value: {e.args[0]}")


@process_camera
def get_value(node_name: str, camera: PySpin.CameraPtr) -> Any:
    """
    Get the value of a camera node.

    Parameters
    ----------
    node_name : str
        The name of the node to get the value of.
    camera : PySpin.CameraPtr, PySpin.CameraList or None, optional
        A pointer to a specific camera instance, a list of instances, or None. If None is specified, all available
        cameras will be considered.

    Returns
    -------
    Any
        The value of the node.
    """
    try:
        assert hasattr(camera, node_name), f"No such node: '{node_name}'"
        node = getattr(camera, node_name)
        assert hasattr(node, 'GetValue'), f"node '{node_name}' has no GetValue() attribute"
        disp_name = node.GetDisplayName()
        assert PySpin.IsReadable(node), f'{disp_name} is not readable'
        return node.GetValue()
    except Exception as e:
        return camera_log(logging.ERROR, camera, f"Error getting value: {e.args[0]}")


@process_camera
def enable_camera_trigger(enable: bool, camera: PySpin.CameraPtr) -> bool:
    """Enable or disable the trigger for a specified camera or all cameras.

    This function allows you to enable or disable the trigger mode for a given camera / given cameras.
    If no camera is specified, it will enable or disable the trigger mode for all available cameras.

    Parameters
    ----------
    enable : bool
        A flag indicating whether to enable (True) or disable (False) the camera trigger.
    camera : PySpin.CameraPtr, PySpin.CameraList or None, optional
        A pointer to a specific camera instance, a list of instances, or None. If None is specified, all available
        cameras will be considered.

    Raises
    ------
    PySpin.SpinnakerException
        If there is an error while setting the trigger mode for the camera.
    """
    return set_value(node_name='TriggerMode', value=int(enable), camera=camera)


@process_camera
def select_line(line: int | str, camera: PySpin.CameraPtr) -> bool:
    return set_value(node_name='LineSelector', value=line, camera=camera)


@process_camera
def set_line_mode(value: int | str, camera: PySpin.CameraPtr) -> bool:
    return set_value(node_name='LineMode', value=value, camera=camera)


@process_camera
def set_line_source(value: int | str, camera: PySpin.CameraPtr) -> bool:
    return set_value(node_name='LineSource', value=value, camera=camera)


@process_camera
def set_framerate(value: float, camera: PySpin.CameraPtr) -> bool:
    return set_value(node_name='AcquisitionFrameRate', value=value, camera=camera)
