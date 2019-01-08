# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Tuesday, November 20th 2018, 9:21:15 am
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 20-11-2018 09:21:34.3434
import shutil
import sys
from pathlib import Path

from pybpodgui_api.models.project import Project


def copy_code_files_to_iblrig_params(iblrig_params_path, task=None,
                                     exclude_filename=None):
    """Copy all files in root tasks folder to iblrig_params_path
    Copy all *.py files in iblrig_path to iblrig_params/IBL/tasks/<task_name>/*
    """
    iblrig_params_path = Path(iblrig_params_path)
    iblrig_params_tasks_path = iblrig_params_path / 'IBL' / 'tasks'
    iblrig_path = iblrig_params_path.parent / 'iblrig'
    iblrig_tasks_path = iblrig_path / 'tasks'

    if exclude_filename is None:
        exclude_filename = 'random_stuff'

    def copy_files(src_folder, dst_folder, glob='*',
                   exclude_filename=exclude_filename):
        src_folder = Path(src_folder)
        dst_folder = Path(dst_folder)
        src_list = [x for x in src_folder.glob(glob)
                    if x.is_file() and exclude_filename not in str(x)]
        for f in src_list:
            shutil.copy(f, dst_folder)
            print(f"Copied {f} to {dst_folder}")

    # Copy all tasks
    tasks = [x for x in iblrig_tasks_path.glob('*') if x.is_dir()]
    if task:
        tasks = [t for t in tasks if task in str(t)]
    else:
        # Copy cleanup, user_settings, path_helper and bonsai_stop
        print('\nS:', str(iblrig_tasks_path), '\nD:', str(iblrig_params_path))
        copy_files(iblrig_tasks_path, iblrig_params_path)

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
    tScreen_execBonsai = tScreen.create_execcmd()
    tScreen_execBonsai.cmd = "python ..\\..\\..\\bonsai_stop.py 7110"
    tScreen_execBonsai.when = tScreen_execBonsai.WHEN_POST

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

    # Create _iblrig_tasks_habituationChoiceWorld
    tHabituation = p.create_task()
    tHabituation.name = '_iblrig_tasks_habituationChoiceWorld'
    tHabituation_execBonsai = tHabituation.create_execcmd()
    tHabituation_execBonsai.cmd = "python ..\\..\\..\\bonsai_stop.py 7110"
    tHabituation_execBonsai.when = tHabituation_execBonsai.WHEN_POST
    tHabituation_execBonsai2 = tHabituation.create_execcmd()
    tHabituation_execBonsai2.cmd = "python ..\\..\\..\\bonsai_stop.py 7111"
    tHabituation_execBonsai2.when = tHabituation_execBonsai2.WHEN_POST
    tHabituation_execCleanup = tHabituation.create_execcmd()
    tHabituation_execCleanup.cmd = "python ..\\..\\..\\cleanup.py"
    tHabituation_execCleanup.when = tHabituation_execCleanup.WHEN_POST

    # Create _iblrig_tasks_trainingChoiceWorld
    tTraining = p.create_task()
    tTraining.name = '_iblrig_tasks_trainingChoiceWorld'
    tTraining_execBonsai = tTraining.create_execcmd()
    tTraining_execBonsai.cmd = "python ..\\..\\..\\bonsai_stop.py 7110"
    tTraining_execBonsai.when = tTraining_execBonsai.WHEN_POST
    tTraining_execBonsai2 = tTraining.create_execcmd()
    tTraining_execBonsai2.cmd = "python ..\\..\\..\\bonsai_stop.py 7111"
    tTraining_execBonsai2.when = tTraining_execBonsai2.WHEN_POST
    tTraining_execCleanup = tTraining.create_execcmd()
    tTraining_execCleanup.cmd = "python ..\\..\\..\\cleanup.py"
    tTraining_execCleanup.when = tTraining_execCleanup.WHEN_POST

    # Create _iblrig_tasks_biasedChoiceWorld
    tBiased = p.create_task()
    tBiased.name = '_iblrig_tasks_biasedChoiceWorld'
    tBiased_execBonsai = tBiased.create_execcmd()
    tBiased_execBonsai.cmd = "python ..\\..\\..\\bonsai_stop.py 7110"
    tBiased_execBonsai.when = tBiased_execBonsai.WHEN_POST
    tBiased_execBonsai2 = tBiased.create_execcmd()
    tBiased_execBonsai2.cmd = "python ..\\..\\..\\bonsai_stop.py 7111"
    tBiased_execBonsai2.when = tBiased_execBonsai2.WHEN_POST
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

    # Create habituationChoiceWorld setup
    habituation = eTasks.create_setup()
    habituation.name = 'habituationChoiceWorld'
    habituation.task = '_iblrig_tasks_habituationChoiceWorld'
    habituation.board = BOARD_NAME
    habituation.detached = True

    # Create trainingChoiceWorld setup
    training = eTasks.create_setup()
    training.name = 'trainingChoiceWorld'
    training.task = '_iblrig_tasks_trainingChoiceWorld'
    training.board = BOARD_NAME
    training.detached = True

    # Create biasedChoiceWorld setup
    biased = eTasks.create_setup()
    biased.name = 'biasedChoiceWorld'
    biased.task = '_iblrig_tasks_biasedChoiceWorld'
    biased.board = BOARD_NAME
    biased.detached = True

    p.save(iblproject_path)

    copy_code_files_to_iblrig_params(iblrig_params_path)

    return


def delete_untracked_files(iblrig_params_path):
    iblrig_params_tasks_path = iblrig_params_path / 'IBL' / 'tasks'
    iblrig_path = iblrig_params_path.parent / 'iblrig'
    iblrig_tasks_path = iblrig_path / 'tasks'
    task_names = [x.name for x in iblrig_tasks_path.glob('*') if x.is_dir()]
    task_paths = [iblrig_params_tasks_path / x for x in task_names]
    for x in task_paths:
        if (x / 'path_helper.py').exists():
            (x / 'path_helper.py').unlink()
        if (x / '_user_settings.py').exists():
            (x / '_user_settings.py').unlink()


# def patch_post_commands(iblproject_path):
#     p = Project()
#     p.load(iblproject_path)
#     for t in p.tasks:
#         for c in t.commands:
#             c.cmd = c.cmd.replace(
#                 ' bonsai_stop.py', ' ..\\..\\..\\bonsai_stop.py')
#             print(c.cmd)
#     p.save(iblproject_path)


def create_subject(iblproject_path, subject_name: str):
    p = Project()
    p.load(iblproject_path)
    if p.find_subject(subject_name) is None:
        subject = p.create_subject()
        subject.name = subject_name
        p.save(iblproject_path)
        print(f"Created subject: {subject_name}")
    else:
        print(f"Skipping creation: Subject {subject.name} already exists")


def create_task(iblproject_path, task_name: str):
    p = Project()
    p.load(iblproject_path)
    task = p.find_task(task_name)
    if task is None:
        task = p.create_task()
        task.name = task_name
        p.save(iblproject_path)
        print(f"Created task: {task_name}")
    else:
        print(f"Skipping creation: Task {task.name} already exists")


def create_task_cleanup_command(task):
    command = task.create_execcmd()
    command.cmd = "python ..\\..\\..\\cleanup.py"
    command.when = command.WHEN_POST
    when = '<POST>' if command.when == 1 else '<PRE>'
    print(f"Added {when} command <{command.cmd}> to {task.name}")

    return task


def create_task_bonsai_stop_command(task, port: int = 7110):
    command = task.create_execcmd()
    command.cmd = f"python ..\\..\\..\\bonsai_stop.py {port}"
    command.when = command.WHEN_POST
    when = '<POST>' if command.when == 1 else '<PRE>'
    print(f"Added {when} command <{command.cmd}> to {task.name}")

    return task


def config_task(iblproject_path, task_name: str):
    p = Project()
    p.load(iblproject_path)
    task = p.find_task(task_name)
    task._commands = []

    if task.name == '_iblrig_calibration_screen':
        task = create_task_bonsai_stop_command(task, port=7110)
        task = create_task_cleanup_command(task)
    if task.name == '_iblrig_calibration_water':
        task = create_task_cleanup_command(task)
    if task.name == '_iblrig_misc_flush_water':
        task = create_task_cleanup_command(task)
    # For all of tasks stop the stim 7110, stop the recording 7111 and cleanup
    if '_iblrig_tasks' in task.name:
        task = create_task_bonsai_stop_command(task, port=7110)
        task = create_task_bonsai_stop_command(task, port=7111)
        task = create_task_cleanup_command(task)

    p.save(iblproject_path)
    print(f"IBL Task configured: {task.name}")


def create_experiment(iblproject_path, exp_name: str):
    p = Project()
    p.load(iblproject_path)
    names = [e.name for e in p.experiments]
    if exp_name not in names:
        exp = p.create_experiment()
        exp.name = exp_name
        p.save(iblproject_path)
        print(f"Created experiment: {exp.name}")
    else:
        print(f"Skipping creation: Experiment {exp.name} already exists")


def create_setup(exp, setup_name: str, board: str, subj: str):
    # task name is defined as the experiment_name + '_' + setup_name
    # Create or get preexisting setup
    setup = [s for s in exp.setups if s.name == setup_name]
    if not setup:
            setup = exp.create_setup()
    else:
        setup = setup[0]

    setup.name = setup_name
    setup.task = exp.name + '_' + setup_name
    setup.board = board
    setup._subjects = []
    setup.subjects + [subj]
    setup.detached = True

    return setup


def create_ibl_setups(iblproject_path, exp_name: str):
    p = Project()
    p.load(iblproject_path)
    exp = [e for e in p.experiments if e.name == exp_name]
    if not e:
        print(f'Experiment {e} not found')
        raise KeyError

    exp = e[0]
    setup_names = [s.name for s in exp.setups]

    if exp.name == '_iblrig_calibration':
        screen = create_setup(exp, 'screen', p.boards[0].name, exp.name)
        water = create_setup(exp, 'water', p.boards[0].name, exp.name)

    if exp.name == '_iblrig_misc':
        flush_water = create_setup(
            exp, 'flush_water', p.boards[0].name, '_iblrig_test_mouse')

    if exp.name == '_iblrig_tasks':
        biasedChoiceWorld = create_setup(
            exp, 'biasedChoiceWorld', p.boards[0].name, None)
        habituationChoiceWorld = create_setup(
            exp, 'habituationChoiceWorld', p.boards[0].name, None)
        trainingChoiceWorld = create_setup(
            exp, 'trainingChoiceWorld', p.boards[0].name, None)

    p.save(iblproject_path)


def create_ibl_project(iblproject_path):
    p = Project()
    try:
        p.load(iblproject_path)
        print()
    except ImportError:
        p.name = 'IBL'
        p.save(iblproject_path)
        print("Created: IBL project")


def create_ibl_board(iblproject_path):
    p = Project()
    p.load(iblproject_path)
    if not p.boards:
        BOARD_NAME = 'SELECT_BOARD_NAME_(e.g.[_iblrig_mainenlab_behavior_0])'
        b = p.create_board()
        b.name = BOARD_NAME
        p.save(iblproject_path)
        print("Created: IBL default board (please remember to rename it)")


def create_ibl_subjects(iblproject_path):
    create_subject(iblproject_path, subject_name='_iblrg_calibration')
    create_subject(iblproject_path, subject_name='_iblrig_test_mouse')
    print("Created: IBL default subjects")


def create_ibl_users(iblproject_path):
    p = Project()
    p.load(iblproject_path)
    if p.find_user('_iblrig_test_user') is None:
        uTest = p.create_user()
        uTest.name = '_iblrig_test_user'
        print("Creating user: _iblrig_test_mouse")
    p.save(iblproject_path)
    print("Created: IBL default user")


def create_ibl_tasks(iblproject_path):
    task_names = [
        '_iblrig_calibration_screen',
        '_iblrig_calibration_water',
        '_iblrig_misc_flush_water',
        '_iblrig_tasks_biasedChoiceWorld',
        '_iblrig_tasks_habituationChoiceWorld',
        '_iblrig_tasks_trainingChoiceWorld',
    ]
    for task_name in task_names:
        create_task(iblproject_path, task_name=task_name)
        config_task(iblproject_path, task_name=task_name)


def create_ibl_experiments(iblproject_path):
    experiment_names = [
        '_iblrig_calibration',
        '_iblrig_misc',
        '_iblrig_tasks',
    ]
    for exp_name in experiment_names:
        create_experiment(iblproject_path, exp_name=exp_name)



def create_ibl_setups(iblproject_path):
    setup_names = [
        'screen',
        'water',
        'flush_water',
        'biasedChoiceWorld',
        'habituationChoiceWorld',
        'trainingChoiceWorld',
    ]
    experiment_names = [
        '_iblrig_calibration',
        '_iblrig_misc',
        '_iblrig_tasks',
    ]
    for exp_name in experiment_names:
        create_setups(iblproject_path, exp_name=exp_name)
    p = Project()
    p.load(iblproject_path)

    p.save(iblproject_path)


def update_pybpod_config(iblrig_params_path):
    """for update to 3.3.1+
    Change location of post script bonsai_stop.py to ..\\..\\..\\bonsai_stop.py
    and remove path_helper.py and _user_settings.py from task code.
    Add habituationChoiceWorld task and setup
    """
    iblrig_params_path = Path(iblrig_params_path)
    iblproject_path = iblrig_params_path / 'IBL'

    create_ibl_project(iblproject_path)
    # patch_post_commands(iblproject_path)
    delete_untracked_files(iblrig_params_path)

    create_ibl_board(iblproject_path)
    create_ibl_subjects(iblproject_path)
    create_ibl_users(iblproject_path)
    create_ibl_tasks(iblproject_path)

    create_ibl_experiments(iblproject_path)
    create_ibl_setups(iblproject_path)


    EXPERIMENT_tasks = [e for e in p.experiments if e.name ==
                        '_iblrig_tasks'][0]

    SETUP_hCW = [s for s in EXPERIMENT_tasks.setups if s.name ==
                 'habituationChoiceWorld']
    if not SETUP_hCW:
        habituation = EXPERIMENT_tasks.create_setup()
        habituation.name = 'habituationChoiceWorld'
        habituation.task = '_iblrig_tasks_habituationChoiceWorld'
        habituation.board = p.boards[0]
        habituation.detached = True

    TASK_hCW = [t for t in p.tasks if t.name ==
                '_iblrig_tasks_habituationChoiceWorld']
    if not TASK_hCW:
        tHabituation = p.create_task()
    else:
        tHabituation = TASK_hCW[0]

    tHabituation.name = '_iblrig_tasks_habituationChoiceWorld'
        tHabituation_execBonsai = tHabituation.create_execcmd()
        tHabituation_execBonsai.cmd = "python ..\\..\\..\\bonsai_stop.py 7110"
        tHabituation_execBonsai.when = tHabituation_execBonsai.WHEN_POST
        tHabituation_execBonsai2 = tHabituation.create_execcmd()
        tHabituation_execBonsai2.cmd = "python ..\\..\\..\\bonsai_stop.py 7111"
        tHabituation_execBonsai2.when = tHabituation_execBonsai2.WHEN_POST
        tHabituation_execCleanup = tHabituation.create_execcmd()
        tHabituation_execCleanup.cmd = "python ..\\..\\..\\cleanup.py"
        tHabituation_execCleanup.when = tHabituation_execCleanup.WHEN_POST

    p.save(iblproject_path)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Please select a path for iblrig_params folder")
    elif len(sys.argv) == 2:
        print(f"Copying task files to: {sys.argv[1]}")
        main(sys.argv[1])
