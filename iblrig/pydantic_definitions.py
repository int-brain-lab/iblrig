from collections import abc
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    AnyUrl,
    BaseModel,
    ConfigDict,
    DirectoryPath,
    Field,
    FilePath,
    PlainSerializer,
    PositiveFloat,
    PositiveInt,
    field_serializer,
    field_validator,
)

from iblrig.constants import BASE_PATH

FilePath = Annotated[FilePath, PlainSerializer(lambda s: str(s), return_type=str)]
"""Validate that path exists and is file. Cast to str upon save."""


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
        raise NotImplementedError


class RigSettings(BunchModel, validate_assignment=True):
    model_config = ConfigDict(title='iblrig_settings.yaml')
    iblrig_local_data_path: Path | None = Field(
        title='IBLRIG local data path', description='The local folder IBLRIG should use for storing data'
    )
    iblrig_local_subjects_path: DirectoryPath | None = Field(
        title='IBLRIG full local data path',
        omit_default=True,
        default=None,
        description='An optional full local data folder (including /Subjects)',
    )
    iblrig_remote_data_path: Path | bool | None = Field(
        title='IBLRIG remote data path', description='The remote folder IBLRIG should use for storing data'
    )
    iblrig_remote_subjects_path: Path | None = Field(
        title='IBLRIG full remote data path',
        omit_default=True,
        default=None,
        description='An optional full remote data folder (including /Subjects)',
    )
    ALYX_USER: str | None = Field(description='Your Alyx username')
    ALYX_URL: AnyUrl | None = Field(title='Alyx URL', description='The URL to your Alyx database')
    ALYX_LAB: str | None = Field(description="Your lab's name as registered on the Alyx database")

    @field_validator('ALYX_USER', 'ALYX_LAB')
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
    OUTPUT: Literal['harp', 'xonar', 'hifi', 'sysdefault']
    COM_SOUND: str | None = None
    AMP_TYPE: Literal['harp', 'AMP2X15'] | None = None
    # ATTENUATION_DB: float = Field(default=0, le=0)


class HardwareSettingsValve(BunchModel):
    WATER_CALIBRATION_DATE: date
    WATER_CALIBRATION_RANGE: list[PositiveFloat] = Field(min_items=2, max_items=2)  # type: ignore
    WATER_CALIBRATION_N: PositiveInt = Field(ge=3, default=5)
    WATER_CALIBRATION_OPEN_TIMES: list[PositiveFloat] = Field(min_items=2)  # type: ignore
    WATER_CALIBRATION_WEIGHT_PERDROP: list[float] = Field(PositiveFloat, min_items=2)  # type: ignore
    FREE_REWARD_VOLUME_UL: PositiveFloat = 1.5


class HardwareSettingsScale(BunchModel):
    COM_SCALE: str | None = None


class HardwareSettingsCamera(BunchModel):
    INDEX: int
    FPS: int | None = Field(
        title='Camera frame rate',
        omit_default=True,
        default=None,
        description='An optional frame rate (for camera QC only)',
        ge=0,
    )
    WIDTH: int | None = Field(
        title='Camera frame width',
        omit_default=True,
        default=None,
        description='An optional frame width (for camera QC only)',
        ge=0,
    )
    HEIGHT: int | None = Field(
        title='Camera frame height',
        omit_default=True,
        default=None,
        description='An optional frame hight (for camera QC only)',
        ge=0,
    )
    SYNC_LABEL: str | None = Field(
        title='Camera DAQ sync label',
        omit_default=True,
        default=None,
        description='The name of the DAQ channel wired to the camera GPIO',
    )


class HardwareSettingsCameraWorkflow(BunchModel):
    setup: FilePath | None = Field(
        title='Optional camera setup workflow',
        omit_default=True,
        default=None,
        description='An optional path to the camera setup Bonsai workflow.',
    )
    recording: FilePath = Field(
        title='Camera recording workflow', description='The path to the Bonsai workflow for camera recording.'
    )

    @field_validator('setup', 'recording', mode='before')
    def valid_path(cls, v):  # noqa: N805
        if not Path(v).is_absolute():  # assume relative to iblrig repo
            v = BASE_PATH.joinpath(v)
        return v


class HardwareSettingsMicrophone(BunchModel):
    BONSAI_WORKFLOW: Path

    @field_serializer('BONSAI_WORKFLOW')
    def serialize_path(self, bonsai_workflow: Path, _info):
        return str(bonsai_workflow)


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
    device_scale: HardwareSettingsScale = HardwareSettingsScale()
    device_cameras: dict[str, dict[str, HardwareSettingsCameraWorkflow | HardwareSettingsCamera]] | None
    device_microphone: HardwareSettingsMicrophone | None = None
    VERSION: str
