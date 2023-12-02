import argparse
from pathlib import Path
import json
import re
import warnings

import yaml
import one.params

UPDATE_FIELDS = {
    None: {'RIG_NAME': 'NAME'},
    'device_bpod': {'COM_BPOD', 'BPOD_TTL_TEST_DATE', 'BPOD_TTL_TEST_STATUS'},
    'device_frame2ttl': {'COM_F2TTL', 'F2TTL_CALIBRATION_DATE',
                         'F2TTL_DARK_THRESH', 'F2TTL_HW_VERSION', 'F2TTL_LIGHT_THRESH'},
    'device_rotary_encoder': {'COM_ROTARY_ENCODER'},
    'device_screen': {'DISPLAY_IDX', 'SCREEN_FREQ_TARGET', 'SCREEN_FREQ_TEST_DATE',
                      'SCREEN_FREQ_TEST_STATUS', 'SCREEN_LUX_DATE', 'SCREEN_LUX_VALUE'},
    'device_valve': {'WATER_CALIBRATION_OPEN_TIMES', 'WATER_CALIBRATION_RANGE',
                     'WATER_CALIBRATION_WEIGHT_PERDROP'},
    'device_sound': {'OUTPUT'}
}


def main(v7_path=None, v8_path=None):

    v7_path = v7_path or Path(Path.home().drive, '/', 'iblrig_params')
    v7_path = v7_path / '.iblrig_params.json'
    v8_path = v8_path or Path(Path.home().drive, '/', 'iblrigv8', 'settings')
    v8_path = v8_path / 'iblrig_settings_template.yaml'
    v8_path_hw = v8_path.with_name('hardware_settings_template.yaml')

    with open(v7_path, 'r') as fp:
        v7_settings = json.load(fp)
    with open(v8_path_hw, 'r') as fp:
        v8_hw_settings = yaml.safe_load(fp)
    with open(v8_path, 'r') as fp:
        v8_settings = yaml.safe_load(fp)

    # Hardware settings
    v8_hw_settings['RIG_NAME'] = v7_settings['NAME']
    v8_hw_settings['MAIN_SYNC'] = 'behavior' in v7_settings['NAME']
    for device, fields in UPDATE_FIELDS.items():
        if device is None:
            for new_field, old_field in fields.items():
                v8_hw_settings[new_field] = v7_settings[old_field]
        elif device == 'device_sound':
            soundcard = 'xonar' if 'behavior' in v7_settings['NAME'] else 'harp'
            v8_hw_settings['device_sound']['OUTPUT'] = soundcard
        else:
            for field in fields:
                v8_hw_settings[device][field] = v7_settings[field]

    with open(v8_path_hw.with_name('hardware_settings.yaml'), 'w') as fp:
        yaml.safe_dump(v8_hw_settings, fp)

    # IBL rig settings
    v8_settings['iblrig_local_data_path'] = v7_settings['DATA_FOLDER_LOCAL']
    v8_settings['iblrig_remote_data_path'] = v7_settings['DATA_FOLDER_REMOTE']
    match = re.match(r'^_iblrig_(\w+)_.*$', v7_settings['NAME'])
    if match:
        lab, = match.groups()
        print(f'Settings ALYX_LAB as "{lab}"')
        v8_settings['ALYX_LAB'] = lab
    else:
        warnings.warn('Unknown lab name, please manually update ALYX_LAB field.')

    # TODO Attempt to load ONE settings for these fields
    v8_settings['ALYX_URL'] = one.params.get_default_client()
    v8_settings['ALYX_USER'] = one.params.get(client=v8_settings['ALYX_URL'], silent=True)

    with open(v8_path.with_name('iblrig_settings.yaml'), 'w') as fp:
        yaml.safe_dump(fp, v8_settings)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Port iblrigv7 settings to iblrigv8")
    parser.add_argument(
        "-v7",
        "--v7-path",
        default=None,
        required=False,
        type=Path,
        help=r"The path to iblrigv7 params folder (default is C:\iblrig_params).",
    )
    parser.add_argument(
        "-v8",
        "--v8-path",
        default=None,
        required=False,
        type=Path,
        help=r"The path to iblrigv8 settings (default is C:\iblrigv8\settings).",
    )
    args = parser.parse_args()
    main(**vars(args))
