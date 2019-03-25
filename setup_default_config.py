# -*- coding:utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date: Tuesday, November 20th 2018, 9:21:15 am
# @Last Modified by: Niccolò Bonacchi
# @Last Modified time: 9-01-2019 10:46:01.011
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
        if (x / 'sound.py').exists():
            (x / 'sound.py').unlink()
        if (x / 'ambient_sensor.py').exists():
            (x / 'ambient_sensor.py').unlink()


def create_subject(iblproject_path, subject_name: str):
    p = Project()
    p.load(iblproject_path)
    if p.find_subject(subject_name) is None:
        subject = p.create_subject()
        subject.name = subject_name
        p.save(iblproject_path)
        print(f"Created subject: {subject_name}")
    else:
        subject = p.find_subject(subject_name)
        print(f"Skipping creation: Subject <{subject.name}> already exists")


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
    when = 'POST' if command.when == 1 else 'PRE'
    print(f"    Added <{when}> command <{command.cmd}> to <{task.name}>")

    return task


def create_task_bonsai_stop_command(task, port: int = 7110):
    command = task.create_execcmd()
    command.cmd = f"python ..\\..\\..\\bonsai_stop.py {port}"
    command.when = command.WHEN_POST
    when = 'POST' if command.when == 1 else 'PRE'
    print(f"    Added <{when}> command <{command.cmd}> to <{task.name}>")

    return task


def create_task_bpod_lights_command(task, onoff: int, when: str = 'POST'):
    command = task.create_execcmd()
    command.cmd = f"python ..\\..\\..\\bpod_lights.py {onoff}"
    if when == 'POST':
        command.when = command.WHEN_POST
    elif when == 'PRE':
        command.when = command.WHEN_PRE

    print(f"    Added <{when}> command <{command.cmd}> to <{task.name}>")

    return task


def create_task_poop_command(task, when: str = 'POST'):
    command = task.create_execcmd()
    command.cmd = f"python ..\\..\\..\\poop_count.py"
    command.when = command.WHEN_POST
    when = 'POST' if command.when == 1 else 'PRE'

    print(f"    Added <{when}> command <{command.cmd}> to <{task.name}>")

    return task


def create_task_create_command(task, when: str = 'POST', patch: bool = True):
    command = task.create_execcmd()
    command.cmd = f"python ..\\..\\..\\create_session.py --patch={patch}"
    if when == 'POST':
        command.when = command.WHEN_POST
    elif when == 'PRE':
        command.when = command.WHEN_PRE

    print(f"    Added <{when}> command <{command.cmd}> to <{task.name}>")

    return task


def config_task(iblproject_path, task_name: str):
    p = Project()
    p.load(iblproject_path)
    task = p.find_task(task_name)
    print(f"  Configuring task <{task.name}>")
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
        task = create_task_bpod_lights_command(task, onoff=1, when='POST')
    if task.name == '_iblrig_tasks_habituationChoiceWorld':
        task = create_task_create_command(task, patch=True)
    if task.name == '_iblrig_tasks_trainingChoiceWorld':
        task = create_task_create_command(task, patch=True)
    if task.name == '_iblrig_tasks_biasedChoiceWorld':
        task = create_task_create_command(task, patch=False)

    p.save(iblproject_path)
    print("    Task configured")


def create_experiment(iblproject_path, exp_name: str):
    p = Project()
    p.load(iblproject_path)
    exp = [e for e in p.experiments if e.name == exp_name]
    if not exp:
        exp = p.create_experiment()
        exp.name = exp_name
        p.save(iblproject_path)
        print(f"Created experiment: {exp.name}")
    else:
        exp = exp[0]
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


def create_experiment_setups(iblproject_path, exp_name: str):
    p = Project()
    p.load(iblproject_path)
    exp = [e for e in p.experiments if e.name == exp_name]
    if not exp:
        print(f'Experiment {exp} not found')
        raise KeyError
    else:
        exp = exp[0]

    if exp.name == '_iblrig_calibration':
        screen = create_setup(exp, 'screen', p.boards[0].name, exp.name)  # noqa
        water = create_setup(exp, 'water', p.boards[0].name, exp.name)  # noqa

    if exp.name == '_iblrig_misc':
        flush_water = create_setup(  # noqa
            exp, 'flush_water', p.boards[0].name, '_iblrig_test_mouse')

    if exp.name == '_iblrig_tasks':
        biasedChoiceWorld = create_setup(  # noqa
            exp, 'biasedChoiceWorld', p.boards[0].name, None)
        habituationChoiceWorld = create_setup(  # noqa
            exp, 'habituationChoiceWorld', p.boards[0].name, None)
        trainingChoiceWorld = create_setup(  # noqa
            exp, 'trainingChoiceWorld', p.boards[0].name, None)

    p.save(iblproject_path)


def create_ibl_project(iblproject_path):
    p = Project()
    try:
        p.load(iblproject_path)
        print(f"Skipping creation: IBL project found <{iblproject_path}>")
    except:  # noqa
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
    else:
        print(f"Skipping creation: Board found with name <{p.boards[0].name}>")


def create_ibl_subjects(iblproject_path):
    create_subject(iblproject_path, subject_name='_iblrig_calibration')
    create_subject(iblproject_path, subject_name='_iblrig_test_mouse')


def create_ibl_users(iblproject_path):
    p = Project()
    p.load(iblproject_path)
    if p.find_user('_iblrig_test_user') is None:
        user = p.create_user()
        user.name = '_iblrig_test_user'
        p.save(iblproject_path)
        print(f"Created: IBL default user <{user.name}>")
    else:
        user = p.find_user('_iblrig_test_user')
        print(f"Skipping creation: User <{user.name}> already exists")


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
    experiment_names = [
        '_iblrig_calibration',
        '_iblrig_misc',
        '_iblrig_tasks',
    ]
    for exp_name in experiment_names:
        print(f"Creating setups for experiment <{exp_name}>")
        create_experiment_setups(iblproject_path, exp_name=exp_name)
    print("Done")


def update_pybpod_config(iblrig_params_path):
    """for update to 3.3.1+
    Change location of post script bonsai_stop.py to ..\\..\\..\\bonsai_stop.py
    and remove path_helper.py and _user_settings.py from task code.
    Add habituationChoiceWorld task and setup
    """
    iblrig_params_path = Path(iblrig_params_path)
    iblproject_path = iblrig_params_path / 'IBL'

    create_ibl_project(iblproject_path)
    delete_untracked_files(iblrig_params_path)

    create_ibl_board(iblproject_path)
    create_ibl_subjects(iblproject_path)
    create_ibl_users(iblproject_path)
    create_ibl_tasks(iblproject_path)

    create_ibl_experiments(iblproject_path)
    create_ibl_setups(iblproject_path)


def main(iblrig_params_path):
    update_pybpod_config(iblrig_params_path)
    copy_code_files_to_iblrig_params(iblrig_params_path)
    return


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Please select a path for iblrig_params folder")
    elif len(sys.argv) == 2:
        print(f"Copying task files to: {sys.argv[1]}")
        main(sys.argv[1])
    # iblrig_params_path = \
    # '/home/nico/Projects/IBL/IBL-github/scratch/IBL_params'
    # iblrig_params_path = Path(iblrig_params_path)
    # iblproject_path = iblrig_params_path / 'IBL'

    # create_ibl_project(iblproject_path)
    # delete_untracked_files(iblrig_params_path)

    # create_ibl_board(iblproject_path)
    # create_ibl_subjects(iblproject_path)
    # create_ibl_users(iblproject_path)
    # create_ibl_tasks(iblproject_path)

    # create_ibl_experiments(iblproject_path)
    # create_ibl_setups(iblproject_path)
    # print('.')
