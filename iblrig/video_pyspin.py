import logging
import time

import PySpin

log = logging.getLogger(__name__)


class Cameras:
    """A class to manage camera instances using the PySpin library.

    This class provides a context manager for initializing and deinitializing
    cameras. It ensures that cameras are properly initialized when entering
    the context and deinitialized when exiting.
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
            for camera in self._cameras:
                camera.Init()

    def __enter__(self) -> PySpin.CameraList:
        """Enters the runtime context related to this object.

        Returns
        -------
        PySpin.CameraList
            The list of initialized cameras.
        """
        return self._cameras

    def __exit__(self, *_):
        """Exits the runtime context related to this object.

        Deinitializes the cameras if they were initialized and releases the system instance.
        """
        if self._init_cameras:
            for camera in self._cameras:
                camera.DeInit()
            del camera  # Clean up the camera reference
        self._cameras.Clear()
        self._instance.ReleaseInstance()

    @property
    def instance(self):
        """Gets the singleton instance of the PySpin system.

        Returns
        -------
        PySpin.System
            The singleton instance of the PySpin system.
        """
        return self._instance


def acquisition_ok() -> bool:
    """Test image acquisition for all available cameras.

    This function attempts to acquire an image from each camera and checks if the acquisition
    was successful. It logs the results of the acquisition test for each camera.

    Returns
    -------
    bool
        True if all cameras successfully acquired an image, False otherwise.
    """
    success = True
    with Cameras() as cameras:
        for camera in cameras:
            log.debug(f'Testing image acquisition with camera #{camera.DeviceID()}')
            camera.BeginAcquisition()
            try:
                image = camera.GetNextImage(1000)
                if image.IsValid() and image.GetImageStatus() == PySpin.SPINNAKER_IMAGE_STATUS_NO_ERROR:
                    log.info(f'Acquisition test for camera #{camera.DeviceID()} was successful.')
                else:
                    log.error(f'Inconsistency detected during acquisition test for camera #{camera.DeviceID()}.')
                    success = False
            except PySpin.SpinnakerException as e:
                log.error(f'Acquisition test for camera #{camera.DeviceID()} failed with an exception: {e.message}')
                success = False
            else:
                if image.IsValid():
                    image.Release()
            finally:
                camera.EndAcquisition()
        del camera
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
        for camera in cameras:
            camera.Init()
            try:
                camera.DeviceReset()
            except PySpin.SpinnakerException as e:
                log.error(f'Error resetting camera #{camera.DeviceID()}: {e}')
            else:
                log.info(f'Resetting camera #{camera.DeviceID.ToString()} ...')
            finally:
                camera.DeInit()

        # Wait for all cameras to come back online
        log.info(f'Waiting for {"camera" if len(cameras) == 1 else "cameras"} to come back online (~10 s) ...')
        all_cameras_online = False
        while not all_cameras_online:
            all_cameras_online = True
            for camera in cameras:
                try:
                    camera.Init()
                except PySpin.SpinnakerException:
                    all_cameras_online = False
                else:
                    log.info(f'Camera #{camera.DeviceID()} is back online.')
                    camera.DeInit()
            if not all_cameras_online:
                time.sleep(0.2)
        del camera


def enable_camera_trigger(enable: bool, camera: PySpin.CameraPtr | None = None):
    """Enable or disable the trigger for a specified camera or all cameras.

    This function allows you to enable or disable the trigger mode for a given camera.
    If no camera is specified, it will enable or disable the trigger mode for all available cameras.

    Parameters
    ----------
    enable : bool
        A flag indicating whether to enable (True) or disable (False) the camera trigger.
    camera : PySpin.CameraPtr | None, optional
        A pointer to a specific camera instance. If None, the function will apply the trigger setting
        to all cameras managed by the Cameras context manager (default is None).
    """
    if camera is None:
        with Cameras() as cameras:
            for cam in cameras:
                enable_camera_trigger(enable=enable, camera=cam)
                del cam
    else:
        node_map = camera.GetNodeMap()
        node_trigger_mode = PySpin.CEnumerationPtr(node_map.GetNode('TriggerMode'))
        node_trigger_mode_value = node_trigger_mode.GetEntryByName('On' if enable else 'Off').GetValue()
        node_trigger_mode.SetIntValue(node_trigger_mode_value)
        log.debug(('Enabled' if enable else 'Disabled') + f' trigger for camera #{camera.DeviceID()}.')
