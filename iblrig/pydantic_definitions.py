from collections import abc
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, field_validator


class BunchModel(BaseModel, abc.MutableMapping):
    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __len__(self):
        return len(self.__dict__)

    def __iter__(self):
        return iter(self.model_fields.keys())

    def items(self):
        return [(key, getattr(self, key)) for key in self.keys()]

    def keys(self):
        return self.model_fields.keys()

    def values(self):
        return (getattr(self, key) for key in self.keys())

    def __delitem__(self, key):
        raise NotImplementedError()


class RigSettings(BunchModel, validate_assignment=True):
    model_config = ConfigDict(title='iblrig_settings.yaml')
    iblrig_local_data_path: Path = Field(
        title='IBLRIG local data path', description='The local folder IBLRIG should use for storing data'
    )
    iblrig_remote_data_path: Path | bool | None = Field(
        title='IBLRIG remote data path', description='The remote folder IBLRIG should use for storing data'
    )
    ALYX_USER: str | None = Field(description='Your Alyx username')
    ALYX_URL: AnyUrl | None = Field(title='Alyx URL', description='The URL to your Alyx database')
    ALYX_LAB: str | None = Field(description="Your lab's name as registered on the Alyx database")

    @field_validator('*')
    def str_must_not_contain_space(cls, v):  # noqa: N805
        if isinstance(v, str) and ' ' in v:
            raise ValueError('must not contain a space')
        return v

    @field_validator('iblrig_remote_data_path')
    def validate_remote_data_path(cls, v):  # noqa: N805
        if isinstance(v, bool) and v:
            raise ValueError()
        return v


class HardwareSettingsBpod(BunchModel):
    COM_BPOD: str | None
    BPOD_TTL_TEST_DATE: date | None = None
    BPOD_TTL_TEST_STATUS: str | None = None
    SOUND_BOARD_BPOD_PORT: Literal['Serial1', 'Serial2', 'Serial3', 'Serial4', 'Serial5', None] = None
    ROTARY_ENCODER_BPOD_PORT: Literal['Serial1', 'Serial2', 'Serial3', 'Serial4', 'Serial5', None] = None


class HardwareSettingsFrame2TTL(BunchModel):
    COM_F2TTL: str | None
    F2TTL_CALIBRATION_DATE: date | None
    F2TTL_DARK_THRESH: int
    F2TTL_HW_VERSION: Literal[1, 2, 3, None]
    F2TTL_LIGHT_THRESH: int


class HardwareSettingsRotaryEncoder(BunchModel):
    COM_ROTARY_ENCODER: str | None


class HardwareSettingsScreen(BunchModel):
    DISPLAY_IDX: Literal[0, 1]
    SCREEN_FREQ_TARGET: int = Field(gt=0)
    SCREEN_FREQ_TEST_DATE: date | None = None
    SCREEN_FREQ_TEST_STATUS: str | None = None
    SCREEN_LUX_DATE: date | None = None
    SCREEN_LUX_VALUE: float | None = None


class HardwareSettingsSound(BunchModel):
    OUTPUT: Literal['harp', 'xonar', 'sysdefault']


class HardwareSettingsValve(BunchModel):
    WATER_CALIBRATION_DATE: date
    WATER_CALIBRATION_RANGE: list[float] = Field(min_items=2, max_items=2)  # type: ignore
    WATER_CALIBRATION_OPEN_TIMES: list[float] = Field(min_items=2)  # type: ignore
    WATER_CALIBRATION_WEIGHT_PERDROP: list[float] = Field(min_items=2)  # type: ignore


class HardwareSettingsCamera(BunchModel):
    BONSAI_WORKFLOW: Path


class HardwareSettingsCameras(BunchModel):
    left: HardwareSettingsCamera | None
    right: HardwareSettingsCamera | None = None
    body: HardwareSettingsCamera | None = None


class HardwareSettingsMicrophone(BunchModel):
    BONSAI_WORKFLOW: Path


class HardwareSettings(BunchModel):
    model_config = ConfigDict(title='hardware_settings.yaml')
    RIG_NAME: str
    MAIN_SYNC: bool
    device_bpod: HardwareSettingsBpod
    device_frame2ttl: HardwareSettingsFrame2TTL
    device_rotary_encoder: HardwareSettingsRotaryEncoder
    device_screen: HardwareSettingsScreen
    device_sound: HardwareSettingsSound
    device_valve: HardwareSettingsValve
    device_cameras: HardwareSettingsCameras | None = None
    device_microphone: HardwareSettingsMicrophone | None = None
    VERSION: str = '1.0.0'
