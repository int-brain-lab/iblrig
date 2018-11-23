# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Tuesday, November 20th 2018, 9:21:15 am
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 20-11-2018 09:21:34.3434
import os
import shutil
import sys
from pathlib import Path

from pybpodgui_api.models.project import Project


def copy_code_files_to_iblrig_params(iblrig_params_path):
    # Copy user_settings and cleanup.py to iblrig_params_path
    # Copy all *.py files in iblrig_path to iblrig_params_path/IBL/tasks/<task_name>/*
    # <task_name> file should be deleted from iblrig_params folder before copying it
    iblrig_params_path = Path(iblrig_params_path)
    iblrig_params_tasks_path = iblrig_params_path / 'IBL' / 'tasks'
    iblrig_path = iblrig_params_path.parent / 'iblrig'
    iblrig_tasks_path = iblrig_path / 'tasks'

    def copy_files(src_folder, dst_folder, glob='*'):
        src_folder = Path(src_folder)
        dst_folder = Path(dst_folder)
        src_list = [x for x in src_folder.glob(glob) if x.is_file()]
        for f in src_list:
            shutil.copy(f, dst_folder)

    # Copy cleanup and user_settings
    print('\nS:',str(iblrig_tasks_path), '\nD:', str(iblrig_params_path))
    copy_files(iblrig_tasks_path, iblrig_params_path)

    # Copy all tasks
    tasks = [x for x in iblrig_tasks_path.glob('*') if x.is_dir()]
    for sf in tasks:
        df = iblrig_params_tasks_path / sf.name
        df.mkdir(parents=True, exist_ok=True)
        copy_files(sf, df)


def main(iblrig_params_path):
    iblrig_params_path = Path(iblrig_params_path)
    iblproject_path = iblrig_params_path / 'IBL'
    # _iblrig_labname_behavior_#
    BOARD_NAME = 'SELECT_BOARD_NAME_(e.g.[_iblrig_mainenlab_behavior_0])'
    # CREATE IBL PROJECT
    p = Project()
    p.name = 'IBL'
    # CREATE BPOD BOARD
    b = p.create_board()
    b.name = BOARD_NAME
    # CREATE SUBJECTS
    sCal = p.create_subject()
    sCal.name = '_iblrig_calibration'
    sTest = p.create_subject()
    sTest.name = '_iblrig_test_mouse'
    # CREATE USERS
    uTest = p.create_user()
    uTest.name = '_iblrig_test_user'

    # CREATE TASKS (EVERYTHING EXCEPT THE ACTUAL CODE - NEED IMPORT FOR THAT)
    # Create _iblrig_calibration_screen
    tScreen = p.create_task()
    tScreen.name = '_iblrig_calibration_screen'
    tScreen_execCleanup = tScreen.create_execcmd()
    tScreen_execCleanup.cmd = "python ..\\..\\..\\cleanup.py"
    tScreen_execCleanup.when = tScreen_execCleanup.WHEN_POST

    # Create _iblrig_calibration_water
    tWater = p.create_task()
    tWater.name = '_iblrig_calibration_water'
    tWater_execCleanup = tWater.create_execcmd()
    tWater_execCleanup.cmd = "python ..\\..\\..\\cleanup.py"
    tWater_execCleanup.when = tWater_execCleanup.WHEN_POST

    # Create _iblrig_misc_flush_water
    tFlush = p.create_task()
    tFlush.name = '_iblrig_misc_flush_water'
    tFlush_execCleanup = tFlush.create_execcmd()
    tFlush_execCleanup.cmd = "python ..\\..\\..\\cleanup.py"
    tFlush_execCleanup.when = tFlush_execCleanup.WHEN_POST

    # Create _iblrig_tasks_basicChoiceWorld
    tBasic = p.create_task()
    tBasic.name = '_iblrig_tasks_basicChoiceWorld'
    tBasic_execBonsai = tBasic.create_execcmd()
    tBasic_execBonsai.cmd = "python bonsai_stop.py"
    tBasic_execBonsai.when = tBasic_execBonsai.WHEN_POST
    tBasic_execCleanup = tBasic.create_execcmd()
    tBasic_execCleanup.cmd = "python ..\\..\\..\\cleanup.py"
    tBasic_execCleanup.when = tBasic_execCleanup.WHEN_POST

    # Create _iblrig_tasks_trainingChoiceWorld
    tTrainingCW = p.create_task()
    tTrainingCW.name = '_iblrig_tasks_trainingChoiceWorld'
    tTrainingCW_execBonsai = tTrainingCW.create_execcmd()
    tTrainingCW_execBonsai.cmd = "python bonsai_stop.py"
    tTrainingCW_execBonsai.when = tTrainingCW_execBonsai.WHEN_POST
    tTrainingCW_execCleanup = tTrainingCW.create_execcmd()
    tTrainingCW_execCleanup.cmd = "python ..\\..\\..\\cleanup.py"
    tTrainingCW_execCleanup.when = tTrainingCW_execCleanup.WHEN_POST

    # Create _iblrig_tasks_biasedChoiceWorld
    tBiased = p.create_task()
    tBiased.name = '_iblrig_tasks_biasedChoiceWorld'
    tBiased_execBonsai = tBiased.create_execcmd()
    tBiased_execBonsai.cmd = "python bonsai_stop.py"
    tBiased_execBonsai.when = tBiased_execBonsai.WHEN_POST
    tBiased_execCleanup = tBiased.create_execcmd()
    tBiased_execCleanup.cmd = "python ..\\..\\..\\cleanup.py"
    tBiased_execCleanup.when = tBiased_execCleanup.WHEN_POST

    # CREATE EXPERIMENTS AND SETUPS
    # Calibration experiment
    eCal = p.create_experiment()
    eCal.name = '_iblrig_calibration'
    # Create screen calibration
    screen = eCal.create_setup()
    screen.name = 'screen'
    screen.task = '_iblrig_calibration_screen'
    screen.board = BOARD_NAME
    screen.subjects + [sCal]  # or screen += sCal
    screen.detached = True
    # Create water calibration
    water = eCal.create_setup()
    water.name = 'water'
    water.task = '_iblrig_calibration_water'
    water.board = BOARD_NAME
    water.subjects + [sCal]  # or water += sCal
    water.detached = True

    # Create _iblrig_misc experiment
    eMisc = p.create_experiment()
    eMisc.name = '_iblrig_misc'
    # Create flush_water setup
    flush_water = eMisc.create_setup()
    flush_water.name = 'flush_water'
    flush_water.task = '_iblrig_misc_flush_water'
    flush_water.board = BOARD_NAME
    flush_water.subjects + [sTest]
    flush_water.detached = True

    # Create _iblrig_tasks experiment
    eTasks = p.create_experiment()
    eTasks.name = '_iblrig_tasks'
    # Create basicChoiceWorld setup
    basic = eTasks.create_setup()
    basic.name = 'basicChoiceWorld'
    basic.task = '_iblrig_tasks_basicChoiceWorld'
    basic.board = BOARD_NAME
    # basic.subjects + [sTest]

    # Create trainingChoiceWorld setup
    training = eTasks.create_setup()
    training.name = 'trainingChoiceWorld'
    training.task = '_iblrig_tasks_trainingChoiceWorld'
    training.board = BOARD_NAME

    # Create biasedChoiceWorld setup
    biased = eTasks.create_setup()
    biased.name = 'biasedChoiceWorld'
    biased.task = '_iblrig_tasks_biasedChoiceWorld'
    biased.board = BOARD_NAME

    p.save(iblproject_path)

    copy_code_files_to_iblrig_params(iblrig_params_path)

    return


if __name__ == "__main__":
    if len(sys.argv) == 1:
        iblrig_params_path = '/home/nico/Projects/IBL/IBL-github/iblrig_params'
        main(iblrig_params_path)
    elif len(sys.argv) == 2:
        print(f"copying task files to {sys.argv[1]}")
        main(sys.argv[1])

