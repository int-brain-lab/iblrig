import argparse
import subprocess

from iblrig.constants import BASE_PATH


def convert_uis():
    parser = argparse.ArgumentParser()
    parser.add_argument('pattern', nargs='?', default='*.*', type=str)
    args = parser.parse_args()

    gui_path = BASE_PATH.joinpath('iblrig', 'gui')
    files = set([f for f in gui_path.glob(args.pattern)])

    for filename_in in files.intersection(gui_path.glob('*.qrc')):
        filename_in = filename_in.relative_to(BASE_PATH)
        filename_out = filename_in.with_stem(filename_in.stem + '_rc').with_suffix('.py')
        print(filename_out)
        args = ['pyrcc5', str(filename_in), '-o', filename_out]
        subprocess.check_output(args, cwd=BASE_PATH)

    for filename_in in files.intersection(gui_path.glob('*.ui')):
        filename_in = filename_in.relative_to(BASE_PATH)
        filename_out = filename_in.with_suffix('.py')
        print(filename_out)
        args = ['pyuic5', str(filename_in), '-o', filename_out, '-x', '--import-from=iblrig.gui']
        subprocess.check_output(args, cwd=BASE_PATH)
