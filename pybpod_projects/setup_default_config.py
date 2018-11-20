# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Tuesday, November 20th 2018, 9:21:15 am
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 20-11-2018 09:21:34.3434
from pybpodgui_api.models.project import Project

# Create IBL project
p = Project()
p.name = 'IBL'
# Create bpod board
b = p.create_board()
b.name = 'SELECT_BOARD_NAME_(e.g.[mainenlab_behavior_box0])'
# Create subjects
sCal = p.create_subject()
sCal.name = '_iblrig_calibration'
sTest = p.create_subject()
sTest.name = '_iblrig_test_mouse'
# Create users
uTest = p.create_user()
uTest.name = '_iblrig_test_user'
# Create/import tasks
tScreen = p.create_task()
tScreen.name = '_iblrig_calibration_screen'
p.import_task()

# Create experiments and setups
eCal = p.create_experiment()
eCal.name = '_iblrig_calibration'
#Create screen calibration
screen = eCal.create_setup()
screen.name = 'screen'
screen.task = '_iblrig_calibration_screen'
screen.board = 'SELECT_BOARD_NAME_(e.g.[mainenlab_behavior_box0])'
screen.subjects + [sCal]  # or screen += sCal
#Create water calibration
screen = eCal.create_setup()
screen.name = 'water'
screen.task = '_iblrig_calibration_water'
screen.board = 'SELECT_BOARD_NAME_(e.g.[mainenlab_behavior_box0])'
screen.subjects + [sCal]  # or screen += sCal

eMisc = p.create_experiment()
eMisc.name = '_iblrig_misc'
flush_water = eMisc.create_setup()
flush_water.name = 'flush_water'
flush_water.task = '_iblrig_misc_flush_water'
flush_water.board = 'SELECT_BOARD_NAME_(e.g.[mainenlab_behavior_box0])'
flush_water.subjects + [sTest]

eTasks = p.create_experiment()
eTasks.name = '_iblrig_tasks'
basic = eTasks.create_setup()
basic.name = 'basicChoiceWorld'
basic.task = '_iblrig_tasks_basicChoiceWorld'
basic.board = 'SELECT_BOARD_NAME_(e.g.[mainenlab_behavior_box0])'
# basic.subjects + [sTest]
