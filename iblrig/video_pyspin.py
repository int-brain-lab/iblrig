import PySpin

from iblutil.util import setup_logger

log = setup_logger('iblrig')


class Instance:
    def __init__(self):
        self._instance = PySpin.System.GetInstance()

    def __enter__(self) -> PySpin.SystemPtr:
        return self._instance

    def __exit__(self, *_):
        self._instance.ReleaseInstance()


class Cameras:
    _instance = None

    def __init__(self, instance: PySpin.SystemPtr | None = None, init_cameras: bool = True):
        if instance is None:
            self._instance = Instance()
            instance = self._instance.__enter__()
        self._cameras = instance.GetCameras()
        if not init_cameras:
            return
        for camera in self._cameras:
            camera.Init()

    def __enter__(self) -> PySpin.CameraList:
        return self._cameras

    def __exit__(self, *_):
        self._cameras.Clear()
        if self._instance is not None:
            self._instance.__exit__()


def configure_trigger(camera: PySpin.CameraPtr, enable: bool):
    node_map = camera.GetNodeMap()
    node_trigger_mode = PySpin.CEnumerationPtr(node_map.GetNode('TriggerMode'))
    node_trigger_mode_value = node_trigger_mode.GetEntryByName('On' if enable else 'Off').GetValue()
    node_trigger_mode.SetIntValue(node_trigger_mode_value)
    log.debug(('Enabled' if enable else 'Disabled') + f' trigger for camera #{camera.DeviceID.ToString()}.')
