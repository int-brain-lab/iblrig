from datetime import date
from ipaddress import IPv4Address
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class RigSettings(BaseModel, validate_assignment=True):
    model_config = ConfigDict(title='iblrig_settings.yaml')
    iblrig_local_data_path: Path = Field(
        title='IBLRIG local data path', description='The local folder IBLRIG should use for storing data'
    )
    iblrig_remote_data_path: Path | bool | None = Field(
        title='IBLRIG remote data path', description='The remote folder IBLRIG should use for storing data'
    )
    ALYX_USER: str = Field(description='Your Alyx username')
    ALYX_URL: HttpUrl | IPv4Address | None = Field(title='Alyx URL', description='The URL to your Alyx database')
    ALYX_LAB: str | None = Field(description="Your lab's name as registered on the Alyx database")

    @field_validator('*')
    def str_must_not_contain_space(cls, v):
        if isinstance(v, str) and ' ' in v:
            raise ValueError('must not contain a space')
        return v

    @field_validator('iblrig_remote_data_path')
    def validate_remote_data_path(cls, v):
        if isinstance(v, bool) and v:
            raise ValueError()
        return v


class HardwareSettingsBpod(BaseModel):
    COM_BPOD: str
    BPOD_TTL_TEST_DATE: date | None = None
    BPOD_TTL_TEST_STATUS: str | None = None
    SOUND_BOARD_BPOD_PORT: Literal['Serial1', 'Serial2', 'Serial3', 'Serial4', 'Serial5', None] = None
    ROTARY_ENCODER_BPOD_PORT: Literal['Serial1', 'Serial2', 'Serial3', 'Serial4', 'Serial5', None] = None


class HardwareSettingsFrame2TTL(BaseModel):
    COM_F2TTL: str
    F2TTL_CALIBRATION_DATE: date | None
    F2TTL_DARK_THRESH: int = Field(gt=0)
    F2TTL_HW_VERSION: Literal[1, 2, 3, None]
    F2TTL_LIGHT_THRESH: int = Field(gt=0)


class HardwareSettingsRotaryEncoder(BaseModel):
    COM_ROTARY_ENCODER: str


class HardwareSettingsScreen(BaseModel):
    DISPLAY_IDX: Literal[0, 1]
    SCREEN_FREQ_TARGET: int = Field(gt=0)
    SCREEN_FREQ_TEST_DATE: date | None = None
    SCREEN_FREQ_TEST_STATUS: str | None = None
    SCREEN_LUX_DATE: date | None = None
    SCREEN_LUX_VALUE: float | None = None


class HardwareSettingsSound(BaseModel):
    OUTPUT: Literal['harp', 'xonar', 'sysdefault']


class HardwareSettingsValve(BaseModel):
    WATER_CALIBRATION_DATE: date
    WATER_CALIBRATION_OPEN_TIMES: list[float] = Field(min_items=2)  # type: ignore
    WATER_CALIBRATION_RANGE: list[float] = Field(min_items=2, max_items=2)  # type: ignore
    WATER_CALIBRATION_WEIGHT_PERDROP: list[float] = Field(min_items=2)  # type: ignore


class HardwareSettingsCamera(BaseModel):
    BONSAI_WORKFLOW: Path


class HardwareSettingsCameras(BaseModel):
    left: HardwareSettingsCamera | None
    right: HardwareSettingsCamera | None = None
    body: HardwareSettingsCamera | None = None


class HardwareSettingsMicrophone(BaseModel):
    BONSAI_WORKFLOW: Path


class HardwareSettings(BaseModel):
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
    device_microphone: HardwareSettingsMicrophone
    VERSION: str = '1.0.0'
