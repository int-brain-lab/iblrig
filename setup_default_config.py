# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Tuesday, November 20th 2018, 9:21:15 am
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 20-11-2018 09:21:34.3434
import os
import sys
from pathlib import Path
from pybpodgui_api.models.project import Project


def main(iblparams_path):
    iblparams_path = Path(iblparams_path)
    iblproject_path = iblparams_path / 'IBL'
    # CREATE IBL PROJECT
    p = Project()
    p.name = 'IBL'
    # CREATE BPOD BOARD
    b = p.create_board()
    b.name = 'SELECT_BOARD_NAME_(e.g.[mainenlab_behavior_box0])'
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

    # Create _iblrig_tasks_ChoiceWorld
    tCW = p.create_task()
    tCW.name = '_iblrig_tasks_ChoiceWorld'
    tCW_execBonsai = tCW.create_execcmd()
    tCW_execBonsai.cmd = "python bonsai_stop.py"
    tCW_execBonsai.when = tCW_exec.WHEN_POST
    tCW_execCleanup = tCW.create_execcmd()
    tCW_execCleanup.cmd = "python ..\\..\\..\\cleanup.py"
    tCW_execCleanup.when = tCW_execCleanup.WHEN_POST

    # CREATE EXPERIMENTS AND SETUPS
    # Calibration experiment
    eCal = p.create_experiment()
    eCal.name = '_iblrig_calibration'
    # Create screen calibration
    screen = eCal.create_setup()
    screen.name = 'screen'
    screen.task = '_iblrig_calibration_screen'
    screen.board = 'SELECT_BOARD_NAME_(e.g.[mainenlab_behavior_box0])'
    screen.subjects + [sCal]  # or screen += sCal
    screen.detached = True
    # Create water calibration
    water = eCal.create_setup()
    water.name = 'water'
    water.task = '_iblrig_calibration_water'
    water.board = 'SELECT_BOARD_NAME_(e.g.[mainenlab_behavior_box0])'
    water.subjects + [sCal]  # or water += sCal
    water.detached = True

    # Create _iblrig_misc experiment
    eMisc = p.create_experiment()
    eMisc.name = '_iblrig_misc'
    # Create flush_water setup
    flush_water = eMisc.create_setup()
    flush_water.name = 'flush_water'
    flush_water.task = '_iblrig_misc_flush_water'
    flush_water.board = 'SELECT_BOARD_NAME_(e.g.[mainenlab_behavior_box0])'
    flush_water.subjects + [sTest]
    flush_water.detached = True

    # Create _iblrig_tasks experiment
    eTasks = p.create_experiment()
    eTasks.name = '_iblrig_tasks'
    # Create basicChoiceWorld setup
    basic = eTasks.create_setup()
    basic.name = 'basicChoiceWorld'
    basic.task = '_iblrig_tasks_basicChoiceWorld'
    basic.board = 'SELECT_BOARD_NAME_(e.g.[mainenlab_behavior_box0])'
    # basic.subjects + [sTest]

    # Create ChoiceWorld setup
    basic = eTasks.create_setup()
    basic.name = 'ChoiceWorld'
    basic.task = '_iblrig_tasks_ChoiceWorld'
    basic.board = 'SELECT_BOARD_NAME_(e.g.[mainenlab_behavior_box0])'

    p.save(iblproject_path)


def copy_code_files_to_iblparams(iblparams_path):
    # Copy user_settings and cleanup.py to iblparams_path
    # Copy all *.py files in iblrig_path to iblparams_path/IBL/tasks/<task_name>/*
    # <task_name> file should be deleted from iblparams folder before copying it
    iblparams_path = Path(iblparams_path)
    iblrig_path = iblparams_path.parent / 'iblrig'


if __name__ == "__main__":
    if len(sys.argv) == 2:
        main(sys.argv[1])
    else:


