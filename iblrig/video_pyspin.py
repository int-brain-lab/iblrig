import functools
import logging
import time
from collections.abc import Callable
from typing import Any

import PySpin
from pydantic import NonNegativeInt

logger = logging.getLogger(__name__)


def camera_log(level: int, camera: PySpin.CameraPtr, message: str, stacklevel: int = 2) -> bool:
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
        if camera is None:
            with Cameras() as camera_list:
                for i in range(len(camera_list)):
                    results.append(func(*args, camera=camera_list[i], **kwargs))
        elif isinstance(camera, PySpin.CameraList):
            for i in range(len(camera)):
                results.append(func(*args, camera=camera[i], **kwargs))
        else:
            results.append(func(*args, camera=camera, **kwargs))

        # return results as tuple
        return tuple(results)

    return wrapper  # type: ignore


def get_node(camera: PySpin.CameraPtr, node_name: str) -> PySpin.INode:
    """
    Retrieve a node from the camera's node map.

    Parameters
    ----------
    camera : PySpin.CameraPtr
        The camera pointer from which to retrieve the node.
    node_name : str
        The name of the node to retrieve.

    Returns
    -------
    PySpin.INode
        The node corresponding to the specified node name.

    Raises
    ------
    AssertionError
        If the node is not available or not readable for the specified camera.
    """
    node_map = camera.GetNodeMap()
    node = node_map.GetNode(node_name)
    assert PySpin.IsAvailable(node), f'Node `{node_name}` is not available'
    assert PySpin.IsReadable(node), f'Node `{node_name}` is not readable'
    return node


def get_enumeration_pointer(camera: PySpin.CameraPtr, node_name: str) -> PySpin.CEnumerationPtr:
    """
    Retrieve a pointer to an enumeration node from the camera's node map.

    Parameters
    ----------
    camera : PySpin.CameraPtr
        The camera pointer from which to retrieve the enumeration node.
    node_name : str
        The name of the enumeration node to retrieve.

    Returns
    -------
    PySpin.CEnumerationPtr
        Pointer to the enumeration node corresponding to the specified node name.

    Raises
    ------
    AssertionError
        If the pointer is not valid for the specified camera.
    """
    node = get_node(camera, node_name)
    pointer = PySpin.CEnumerationPtr(node)
    assert pointer.IsValid(), f'Invalid CEnumerationPtr `{node_name}`'
    return pointer


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
        logger.info(f'Waiting for {"camera" if len(cameras) == 1 else "cameras"} to come back online (~10 s) ...')
        all_cameras_online = False
        while not all_cameras_online:
            all_cameras_online = True
            for i in range(len(cameras)):
                try:
                    cameras[i].Init()
                except PySpin.SpinnakerException:
                    all_cameras_online = False
                else:
                    camera_log(logging.INFO, cameras[i], 'Back online.')
                    cameras[i].DeInit()
            if not all_cameras_online:
                time.sleep(0.2)


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
    try:
        trigger_mode_ptr = get_enumeration_pointer(camera, 'TriggerMode')
        trigger_mode_val = trigger_mode_ptr.GetEntryByName('On' if enable else 'Off').GetValue()
        if trigger_mode_ptr.GetIntValue() != trigger_mode_val:
            trigger_mode_ptr.SetIntValue(trigger_mode_val)
            camera_log(logging.INFO, camera, f'{"Enabled" if enable else "Disabled"} trigger')
        return True
    except Exception as e:
        return camera_log(logging.ERROR, camera, f'Error setting trigger: {e.args[0]}')


def set_enumeration_int(node_name: str, value: int, camera: PySpin.CameraPtr) -> bool:
    try:
        pointer = get_enumeration_pointer(camera, node_name)
        node_name_pretty = pointer.GetDisplayName()
        valid_values = range(len(pointer.GetEntries()))
        assert value in valid_values, f'Value must be in the range 0..{range(4).stop - 1}'
        if pointer.GetIntValue() != value:
            assert 'W' in PySpin.EAccessModeClass_ToString(pointer.GetAccessMode()), f'{node_name_pretty} is not writable'
            pointer.SetIntValue(value)
            camera_log(logging.INFO, camera, f'{node_name_pretty} set to {pointer.GetEntry(value).GetDisplayName()}')
        return True
    except Exception as e:
        return camera_log(logging.ERROR, camera, f'Error setting {node_name}: {e.args[0]}')


def set_enumeration_str(node_name: str, value: str, camera: PySpin.CameraPtr) -> bool:
    try:
        pointer = get_enumeration_pointer(camera, node_name)
        node_name_pretty = pointer.GetDisplayName()
        valid_values = [x.GetDisplayName() for x in pointer.GetEntries()]
        assert value in valid_values, f'Invalid {node_name_pretty}: `{value}`. Valid values are ' + ', '.join(
            [f'`{x}`' for x in valid_values]
        )
        int_value = pointer.GetEntryByName(value).GetValue()
        if pointer.GetIntValue() != int_value:
            assert 'W' in PySpin.EAccessModeClass_ToString(pointer.GetAccessMode()), f'{node_name_pretty} is not writable'
            pointer.SetIntValue(int_value)
            camera_log(logging.INFO, camera, f'{node_name} set to `{value}`')
        return True
    except Exception as e:
        return camera_log(logging.ERROR, camera, f'Error setting {node_name}: {e.args[0]}')


@process_camera
def select_line(line: NonNegativeInt, camera: PySpin.CameraPtr) -> bool:
    return set_enumeration_int(node_name='LineSelector', value=line, camera=camera)


@process_camera
def set_line_mode(value: str, camera: PySpin.CameraPtr) -> bool:
    return set_enumeration_str(node_name='LineMode', value=value, camera=camera)


@process_camera
def set_line_source(value: str, camera: PySpin.CameraPtr) -> bool:
    return set_enumeration_str(node_name='LineSource', value=value, camera=camera)
