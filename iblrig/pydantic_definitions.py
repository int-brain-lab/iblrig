from collections import abc
from datetime import date
from pathlib import Path
from typing import Annotated, Any, Literal

import pandas as pd
from annotated_types import Ge, Le
from pydantic import (
    AnyUrl,
    BaseModel,
    ConfigDict,
    DirectoryPath,
    Field,
    FilePath,
    NonNegativeFloat,
    NonNegativeInt,
    PlainSerializer,
    PositiveFloat,
    PositiveInt,
    field_serializer,
    field_validator,
    model_validator,
)
from pydantic_core._pydantic_core import PydanticUndefined
from typing_extensions import Self

from iblrig.constants import BASE_PATH

ExistingFilePath = Annotated[FilePath, PlainSerializer(lambda s: str(s), return_type=str)]
"""Validate that path exists and is file. Cast to str upon save."""

BehaviourInputPort = Annotated[int, Ge(1), Le(4)]


class BunchModel(BaseModel, abc.MutableMapping):
    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __len__(self):
        return len(self.__dict__)

    def __iter__(self):
        return iter(self.__class__.model_fields.keys())

    def items(self):
        return [(key, getattr(self, key)) for key in self.keys()]

    def keys(self):
        return self.__class__.model_fields.keys()

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
        default=None,
        description='An optional full local data folder (including /Subjects)',
    )
    iblrig_remote_data_path: Path | bool | None = Field(
        title='IBLRIG remote data path', description='The remote folder IBLRIG should use for storing data'
    )
    iblrig_remote_subjects_path: Path | None = Field(
        title='IBLRIG full remote data path',
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
    DISABLE_BEHAVIOR_INPUT_PORTS: list[BehaviourInputPort] = [2, 3, 4]
    USE_AMBIENT_MODULE: bool = True


class HardwareSettingsFrame2TTL(BunchModel):
    COM_F2TTL: str | None
    F2TTL_CALIBRATION_DATE: date | None
    F2TTL_DARK_THRESH: int
    F2TTL_LIGHT_THRESH: int


class HardwareSettingsRotaryEncoder(BunchModel):
    COM_ROTARY_ENCODER: str | None
    WHEEL_DIAMETER_MM: float = 62.0


class HardwareSettingsScreen(BunchModel):
    DISPLAY_IDX: int = Field(ge=0, le=1)  # -1 = Default, 0 = First, 1 = Second, 2 = Third, etc
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
    WATER_CALIBRATION_RANGE: list[PositiveFloat] = Field(min_length=2, max_length=2)  # type: ignore
    WATER_CALIBRATION_N: PositiveInt = Field(ge=3, default=5)
    WATER_CALIBRATION_OPEN_TIMES: list[PositiveFloat] = Field(min_length=2)  # type: ignore
    WATER_CALIBRATION_WEIGHT_PERDROP: list[float] = Field(PositiveFloat, min_length=2)  # type: ignore
    FREE_REWARD_VOLUME_UL: PositiveFloat = 1.5


class HardwareSettingsScale(BunchModel):
    COM_SCALE: str | None = None


class HardwareSettingsCameraParameters(BunchModel):
    LABEL: str = Field(title='Camera label', description="The camera's label", exclude=True)
    SYNC_LABEL: str | None = Field(
        title='Camera DAQ sync label',
        default=None,
        description='The name of the DAQ channel wired to the camera GPIO',
    )
    INDEX: NonNegativeInt | None = Field(
        title='Camera Index',
        default=None,
        description="The camera's index as reported by FlyCapture",
        deprecated='Use of INDEX is deprecated. Please use SERIAL instead.',
    )
    SERIAL: str | None = Field(
        title='Camera serial number', default=None, description="The camera's serial number as reported by FlyCapture"
    )
    FPS: PositiveInt | None = Field(
        title='Camera frame rate',
        default=None,
        description='An optional frame rate',
    )
    VIDEO_MODE: NonNegativeInt = Field(
        title='Video Mode',
        default=0,
        description='Current video mode',
        ge=0,
        le=1,
    )
    WIDTH: PositiveInt | None = Field(
        title='Camera frame width',
        default=None,
        description='An optional frame width',
    )
    HEIGHT: PositiveInt | None = Field(
        title='Camera frame height',
        default=None,
        description='An optional frame height',
    )
    EXPOSURE_TIME_US: PositiveFloat = Field(
        title='Exposure Time',
        default=10000,
        description='Exposure time in microseconds',
    )
    EXPOSURE_COMPENSATION_EV: float = Field(
        title='Camera exposure compensation',
        default=0.7,
        description='The measured or target image plane illuminance in EV',
    )
    BLACK_LEVEL: NonNegativeFloat = Field(
        title='Black Level',
        default=2,
        description='Analog black level in percent',
    )
    GAIN_DB: NonNegativeFloat = Field(
        title='Gain',
        default=12,
        description='Gain applied to the image in dB',
    )
    LINE_MODE: list[Literal['Input', 'Output']] = Field(
        title='Line Mode',
        default=['Input', 'Output', 'Output', 'Input'],
        description='Controls whether the physical Line is used to Input or Output a signal',
        min_length=2,
        max_length=2,
    )
    LINE_SOURCE: list[Literal['ExposureActive', 'ExternalTriggerActive', 'UserOutput2'], None] = Field(
        title='Line Source',
        default=[None, 'ExposureActive', 'ExposureActive', None],
        description='Selects which internal acquisition or I/O source signal to output on the selected line',
        min_length=2,
        max_length=2,
    )
    STROBE_DURATION_US: list[NonNegativeFloat] = Field(
        title='Strobe Duration',
        default=[None, 10e3, 10e3, None],
        description='Sets the duration (in microseconds) of the Strobe Signal',
        min_length=2,
        max_length=2,
    )
    STROBE_DELAY_US: list[NonNegativeFloat] = Field(
        title='Strobe Delay',
        default=[None, 0, 0, None],
        description='Sets the duration (in microseconds) of the delay before starting the Strobe Signal.',
        min_length=2,
        max_length=2,
    )

    @model_validator(mode='after')
    def check_index_or_serial(self) -> Self:
        if self.INDEX is None and self.SERIAL is None:
            raise ValueError('Either SERIAL or INDEX is required')
        return self


class HardwareSettingsNeurophotometrics(BunchModel):
    DEVICE_MODEL: Literal['NP3002'] = 'NP3002'
    BONSAI_EXECUTABLE: ExistingFilePath = Path.home().joinpath('AppData', 'Local', 'Bonsai', 'Bonsai.exe')
    BONSAI_WORKFLOW: Path = Path('devices', 'neurophotometrics', 'FP3002.bonsai')
    BONSAI_WORKFLOW_DAQ: Path = Path('devices', 'neurophotometrics', 'FP3002_daq.bonsai')
    COM_NEUROPHOTOMETRY: str | None = None


class HardwareSettingsCameraWorkflow(BunchModel):
    setup: ExistingFilePath | None = Field(
        title='Optional camera setup workflow',
        default=None,
        description='An optional path to the camera setup Bonsai workflow.',
    )
    recording: ExistingFilePath = Field(
        title='Camera recording workflow', description='The path to the Bonsai workflow for camera recording.'
    )

    @field_validator('setup', 'recording', mode='before')
    def valid_path(cls, v):  # noqa: N805
        if not Path(v).is_absolute():  # assume relative to iblrig repo
            v = BASE_PATH.joinpath(v)
        return v


class HardwareSettingsCameraProfile(BunchModel, extra='allow'):
    """Pydantic Model for a camera profile, defining BONSAI workflows and parameters for one or multiple cameras."""

    BONSAI_WORKFLOW: HardwareSettingsCameraWorkflow

    @model_validator(mode='before')
    @classmethod
    def parse_extra_as_camera_parameters(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Validate all fields other than BONSAI_WORKFLOW as HardwareSettingsCameraParameters."""
        if len(data) == 1:
            raise ValueError('Parameters for at least one camera must be specified.')
        for key, val in list(data.items()):
            if key != 'BONSAI_WORKFLOW':
                val['LABEL'] = key  # So we can assess the camera label from within the sub-model
                data[key] = HardwareSettingsCameraParameters.model_validate(val)
        return data


class HardwareSettingsCamera(BunchModel, extra='allow'):
    """Pydantic Model for cameras, containing one or several camera profiles."""

    @model_validator(mode='before')
    @classmethod
    def parse_extra_as_camera_profiles(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Validate all fields as HardwareSettingsCameraProfile."""
        if len(data) == 0:
            raise ValueError('At least one camera profile must be specified.')
        return {key: HardwareSettingsCameraProfile.model_validate(val) for key, val in data.items()}


class HardwareSettingsMicrophone(BunchModel):
    BONSAI_WORKFLOW: Path

    @field_serializer('BONSAI_WORKFLOW')
    def serialize_path(self, bonsai_workflow: Path, _info):
        return str(bonsai_workflow)


class HardwareSettings(BunchModel):
    model_config = ConfigDict(title='hardware_settings.yaml')
    RIG_NAME: str
    MAIN_SYNC: bool
    device_bpod: HardwareSettingsBpod | None = None
    device_frame2ttl: HardwareSettingsFrame2TTL | None = None
    device_rotary_encoder: HardwareSettingsRotaryEncoder | None = None
    device_screen: HardwareSettingsScreen | None = None
    device_sound: HardwareSettingsSound | None = None
    device_valve: HardwareSettingsValve | None = None
    device_scale: HardwareSettingsScale = HardwareSettingsScale()
    device_cameras: HardwareSettingsCamera | None
    device_microphone: HardwareSettingsMicrophone | None = None
    device_neurophotometrics: HardwareSettingsNeurophotometrics | None = None
    VERSION: str


class TrialDataModel(BaseModel):
    """
    A data model for trial data that extends BaseModel.

    This model allows for the addition of extra fields beyond those defined in the model.
    """

    model_config = ConfigDict(extra='allow')  # allow adding extra fields

    @classmethod
    def preallocate_dataframe(cls, n_rows: int) -> pd.DataFrame:
        """
        Preallocate a DataFrame with specified number of rows, using default values or pandas.NA.

        This method creates a pandas DataFrame with the same columns as the fields defined in the Pydantic model.
        Each column is initialized with the field's default value if available, otherwise with pandas.NA.

        We use Pandas.NA for default values rather than NaN, None or Zero. This allows us to clearly indicate missing
        values - which will raise a Pydantic ValidationError.

        Parameters
        ----------
        n_rows : int
            The number of rows to create in the DataFrame.

        Returns
        -------
        pd.DataFrame
            A DataFrame with `n_rows` rows and columns corresponding to the model's fields.
        """
        data = {}
        for field, field_info in cls.model_fields.items():
            default_value = field_info.default if field_info.default is not PydanticUndefined else pd.NA
            data[field] = [default_value] * n_rows
        return pd.DataFrame(data)

        # # Create a NumPy array for the data
        # data_array = np.empty((n_rows, len(cls.model_fields)), dtype=object)
        #
        # # Fill default values
        # for i, (field, field_info) in enumerate(cls.model_fields.items()):
        #     if (default_value := field_info.default) is not PydanticUndefined:
        #         data_array[:, i] = default_value
        #
        # # Map model's dtypes to pandas nullable types
        # dtypes = {name: field.annotation for name, field in cls.model_fields.items()}
        # dtype_mapping = {
        #     int: pd.Int64Dtype(),
        #     float: pd.Float64Dtype(),
        #     bool: pd.BooleanDtype(),
        #     str: pd.StringDtype(),
        # }
        # nullable_dtypes = {name: dtype_mapping.get(dtype, object) for name, dtype in dtypes.items()}
        #
        # # Create empty DataFrame with specified dtypes
        # df = pd.DataFrame(data_array, columns=cls.model_fields.keys()).astype(nullable_dtypes)
        #
        # return df
