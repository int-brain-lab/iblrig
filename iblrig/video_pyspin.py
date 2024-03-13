import logging

import PySpin

log = logging.getLogger(__name__)


class Cameras:
    _instance = None

    def __init__(self, init_cameras: bool = True):
        self._instance = PySpin.System.GetInstance()
        self._cameras = self._instance.GetCameras()
        if not init_cameras:
            return
        for camera in self._cameras:
            camera.Init()

    def __enter__(self) -> PySpin.CameraList:
        return self._cameras

    def __exit__(self, *_):
        self._cameras.Clear()
        self._instance.ReleaseInstance()

    @property
    def instance(self):
        return self._instance


def enable_camera_trigger(enable: bool, camera: PySpin.CameraPtr | None = None):
    if camera is None:
        with Cameras() as cameras:
            for camera in cameras:
                enable_camera_trigger(enable=enable, camera=camera)
            del camera
    else:
        node_map = camera.GetNodeMap()
        node_trigger_mode = PySpin.CEnumerationPtr(node_map.GetNode('TriggerMode'))
        node_trigger_mode_value = node_trigger_mode.GetEntryByName('On' if enable else 'Off').GetValue()
        node_trigger_mode.SetIntValue(node_trigger_mode_value)
        log.info(('Enabled' if enable else 'Disabled') + f' trigger for camera #{camera.DeviceID.ToString()}.')
