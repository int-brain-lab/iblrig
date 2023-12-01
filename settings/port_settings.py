import argparse
from pathlib import Path
import yaml
import json

UPDATE_FIELDS = {
    None: {'RIG_NAME': 'NAME'},
    'device_bpod': {'COM_BPOD', 'BPOD_TTL_TEST_DATE', 'BPOD_TTL_TEST_STATUS'},
    'device_frame2ttl': {'COM_F2TTL', 'F2TTL_CALIBRATION_DATE',
                         'F2TTL_DARK_THRESH', 'F2TTL_HW_VERSION', 'F2TTL_LIGHT_THRESH'},
    'device_rotary_encoder': {'COM_ROTARY_ENCODER'},
    'device_screen': {'DISPLAY_IDX', 'SCREEN_FREQ_TARGET', 'SCREEN_FREQ_TEST_DATE',
                      'SCREEN_FREQ_TEST_STATUS', 'SCREEN_LUX_DATE', 'SCREEN_LUX_VALUE'},

}


def main(v7_path=None, v8_path=None):

    v7_path = v7_path or Path(Path.home().drive, '/', 'iblrig_params', '.iblrig_params.json')
    v8_path = v8_path or Path(Path.home().drive, '/', 'iblrigv8', 'settings', 'iblrig_settings_template.yaml')
    v8_path_hw = v8_path.with_name('hardware_settings_template.yaml')

    with open(v7_path, 'r') as fp:
        v7_settings = json.load(fp)
    with open(v8_path_hw, 'r') as fp:
        v8_hw_settings = yaml.safe_load(fp)
    with open(v8_path, 'r') as fp:
        v8_settings = yaml.safe_load(fp)

    v8_hw_settings['RIG_NAME'] = v7_settings['NAME']
    for device, fields in UPDATE_FIELDS.items():
        if device is None:
            for new_field, old_field in fields.items():
                v8_hw_settings[new_field] = v7_settings[old_field]
        else:
            for field in fields:
                v8_hw_settings[device][field] = v7_settings[field]

    v8_hw_settings['device_sound']['OUTPUT'] = 'xonar' if 'behavior' in v7_settings['NAME'] else 'harp'
    v8_hw_settings['device_valve']['WATER_CALIBRATION_OPEN_TIMES'] = v7_settings['WATER_CALIBRATION_OPEN_TIMES']
    v8_hw_settings['device_valve']['WATER_CALIBRATION_RANGE'] = v7_settings['WATER_CALIBRATION_RANGE']
    v8_hw_settings['device_valve']['WATER_CALIBRATION_WEIGHT_PERDROP'] = v7_settings['WATER_CALIBRATION_WEIGHT_PERDROP']

    with open(v8_path_hw.with_name('hardware_settings.yaml'), 'w') as fp:
        yaml.safe_dump(v8_hw_settings, fp)
    # with open(v8_path.with_name('iblrig_settings.yaml'), 'w') as fp:
    #     yaml.safe_dump(fp, v8_settings)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Port iblrigv7 settings to iblrigv8")
    parser.add_argument('mouse', help='Mouse name')
    parser.add_argument(
        "-t",
        "--training",
        default=False,
        required=False,
        action="store_true",
        help="Launch video workflow for biasedCW session on ephys rig.",
    )
    parser.add_argument(
        "--ignore-checks",
        default=False,
        required=False,
        action="store_true",
        help="Ignore ibllib and iblscripts checks",
    )
    args = parser.parse_args()
