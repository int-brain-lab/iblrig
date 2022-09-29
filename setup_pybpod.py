import os
import shutil
import sys
from pathlib import Path

from pybpodgui_api.models.project import Project

IBLRIG_FOLDER = Path(__file__).absolute().parent
IBLRIG_PARAMS_FOLDER = IBLRIG_FOLDER.parent / "iblrig_params"


def delete_untracked_files(iblrig_params_path):
    print("Deleting untracked files")
    iblrig_params_tasks_path = iblrig_params_path / "IBL" / "tasks"
    iblrig_tasks_path = iblrig_params_path.parent / "iblrig" / "tasks"
    task_names = [x.name for x in iblrig_tasks_path.glob("*") if x.is_dir()]
    task_paths = [iblrig_params_tasks_path / x for x in task_names]
    # Delete old files from all task folders
    for x in task_paths:
        (x / "path_helper.py").unlink() if (x / "path_helper.py").exists() else None
        (x / "_user_settings.py").unlink() if (x / "_user_settings.py").exists() else None
        (x / "user_settings.py").unlink() if (x / "user_settings.py").exists() else None
        (x / "sound.py").unlink() if (x / "sound.py").exists() else None
        (x / "ambient_sensor.py").unlink() if (x / "ambient_sensor.py").exists() else None

    # Remove python files that are in iblrig/scripts from root of params folder
    for f in IBLRIG_PARAMS_FOLDER.glob("*.py"):
        f.unlink()
        print(f"  Removed: {f}")
    # Remove Bonsai.Video preview folders from packages
    packages = IBLRIG_FOLDER / "Bonsai" / "Packages"
    vid = packages / "Bonsai.Video.2.4.0-preview"
    viddes = packages / "Bonsai.Video.Design.2.4.0-preview"
    shutil.rmtree(vid) if vid.exists() else None
    shutil.rmtree(viddes) if viddes.exists() else None

    # Remove whole task from iblrig_params
    task = [x for x in task_paths if "_iblrig_misc_sync_test" in x.name]
    if task:
        print("Removing:", task)
        task = task[0]
        shutil.rmtree(task)


def copy_pybpod_user_settings():
    print("Copying general PyBpod IBL project settings")
    src_file = IBLRIG_FOLDER / "scripts" / "user_settings.py"
    dst_file = IBLRIG_PARAMS_FOLDER / "user_settings.py"
    shutil.copy(str(src_file), str(dst_file))
    print(f" Copied: {src_file} to {dst_file}")


def create_ibl_project(iblproject_path):
    p = Project()
    print("Creating IBL project")
    try:
        p.load(iblproject_path)
        print(f"  Skipping creation: IBL project found in: {iblproject_path}")
    except:  # noqa
        p.name = "IBL"
        p.save(iblproject_path)
        print("  Created: IBL project")


def create_ibl_board(iblproject_path):
    print("Creating: Bpod board")
    p = Project()
    p.load(iblproject_path)
    if not p.boards:
        BOARD_NAME = "SELECT_BOARD_NAME_(e.g.[_iblrig_mainenlab_behavior_0])"
        b = p.create_board()
        b.name = BOARD_NAME
        b.serial_port = "COM#"
        p.save(iblproject_path)
        print("  Created: IBL default board (please remember to rename it)")
    else:
        print(f"  Skipping creation: Board found with name <{p.boards[0].name}>")


def create_subject(iblproject_path, subject_name: str):
    p = Project()
    p.load(iblproject_path)
    subject = p.create_subject()
    subject.name = subject_name
    p.save(iblproject_path)
    print(f"  Created subject: {subject_name}")


def create_ibl_subjects(iblproject_path):
    print("Creating default subjects")
    create_subject(iblproject_path, subject_name="_iblrig_calibration")
    create_subject(iblproject_path, subject_name="_iblrig_test_mouse")


def create_ibl_users(iblproject_path):
    print("Creating default user")
    p = Project()
    p.load(iblproject_path)
    if p.find_user("_iblrig_test_user") is None:
        user = p.create_user()
        user.name = "_iblrig_test_user"
        p.save(iblproject_path)
        print(f"  Created: IBL default user <{user.name}>")
    else:
        user = p.find_user("_iblrig_test_user")
        print(f"  Skipping creation: User <{user.name}> already exists")


def create_task(iblproject_path, task_name: str):
    p = Project()
    p.load(iblproject_path)
    task = p.create_task()
    task.name = task_name
    p.save(iblproject_path)
    print(f"Created task: {task_name}")


def create_task_cleanup_command(task):
    command = task.create_execcmd()
    fil = str(IBLRIG_FOLDER / "scripts" / "cleanup.py")
    command.cmd = f"python {fil}"
    command.when = command.WHEN_POST
    when = "POST" if command.when == 1 else "PRE"
    print(f"    Added <{when}> command <{command.cmd}> to <{task.name}>")

    return task


def create_task_bonsai_stop_command(task, port: int = 7110):
    command = task.create_execcmd()
    fil = str(IBLRIG_FOLDER / "scripts" / "bonsai_stop.py")
    command.cmd = f"python {fil} {port}"
    command.when = command.WHEN_POST
    when = "POST" if command.when == 1 else "PRE"
    print(f"    Added <{when}> command <{command.cmd}> to <{task.name}>")

    return task


def create_task_bpod_lights_command(task, onoff: int, when: str = "POST"):
    command = task.create_execcmd()
    fil = str(IBLRIG_FOLDER / "scripts" / "bpod_lights.py")
    command.cmd = f"python {fil} {onoff}"
    if when == "POST":
        command.when = command.WHEN_POST
    elif when == "PRE":
        command.when = command.WHEN_PRE

    print(f"    Added <{when}> command <{command.cmd}> to <{task.name}>")

    return task


def create_task_poop_command(task, when: str = "POST"):
    command = task.create_execcmd()
    fil = str(IBLRIG_FOLDER / "scripts" / "poop_count.py")
    command.cmd = f"python {fil}"
    command.when = command.WHEN_POST
    when = "POST" if command.when == 1 else "PRE"

    print(f"    Added <{when}> command <{command.cmd}> to <{task.name}>")

    return task


def create_task_create_command(task, when: str = "POST", poop: bool = True):
    command = task.create_execcmd()
    fil = str(IBLRIG_FOLDER / "scripts" / "create_session.py")
    command.cmd = f"python {fil} --poop={poop}"
    if when == "POST":
        command.when = command.WHEN_POST
    elif when == "PRE":
        command.when = command.WHEN_PRE

    print(f"    Added <{when}> command <{command.cmd}> to <{task.name}>")

    return task


def create_task_move_passive_command(task, when: str = "POST"):  # TODO: Ensure that this is desired behavior
    command = task.create_execcmd()
    fil = str(IBLRIG_FOLDER / "scripts" / "move_passive.py")
    command.cmd = f"python {fil}"
    if when == "POST":
        command.when = command.WHEN_POST
    elif when == "PRE":
        command.when = command.WHEN_PRE

    print(f"    Added <{when}> command <{command.cmd}> to <{task.name}>")

    return task


def config_task(iblproject_path, task_name: str):  # XXX: THIS!
    p = Project()
    p.load(iblproject_path)
    task = p.find_task(task_name)
    print(f"  Configuring task <{task.name}>")
    task._commands = []

    if task.name == "_iblrig_calibration_screen":
        task = create_task_bonsai_stop_command(task, port=7110)
        task = create_task_cleanup_command(task)
    if task.name == "_iblrig_calibration_water":
        task = create_task_cleanup_command(task)
    if task.name == "_iblrig_calibration_input_listner":
        task = create_task_cleanup_command(task)
    if task.name == "_iblrig_calibration_frame2TTL":
        task = create_task_cleanup_command(task)
    if task.name == "_iblrig_misc_flush_water":
        task = create_task_cleanup_command(task)
    if task.name == "_iblrig_misc_bpod_ttl_test":
        task = create_task_bonsai_stop_command(task, port=7110)
        task = create_task_cleanup_command(task)
    if task.name == "_iblrig_misc_frame2TTL_freq_test":
        task = create_task_cleanup_command(task)
    # For all bpod tasks turn off bpod lights, stop the stim 7110, stop the camera 7111 and cleanup
    btasks = [
        "_iblrig_tasks_habituationChoiceWorld",
        "_iblrig_tasks_trainingChoiceWorld",
        "_iblrig_tasks_biasedChoiceWorld",
        "_iblrig_tasks_ephysChoiceWorld",
    ]
    if task.name in btasks:
        task = create_task_bonsai_stop_command(task, port=7110)  # visual stimulus
        task = create_task_bonsai_stop_command(task, port=7111)  # camera recording
        task = create_task_cleanup_command(task)
        task = create_task_bpod_lights_command(task, 0, when="PRE")
        task = create_task_bpod_lights_command(task, 1, when="POST")
    if task.name == "_iblrig_tasks_habituationChoiceWorld":
        task = create_task_create_command(task, poop=True)
        task = create_task_bonsai_stop_command(task, port=7112)  # record_mic
    if task.name == "_iblrig_tasks_trainingChoiceWorld":
        task = create_task_create_command(task, poop=True)
        task = create_task_bonsai_stop_command(task, port=7112)  # record_mic
    if task.name == "_iblrig_tasks_biasedChoiceWorld":
        task = create_task_create_command(task, poop=True)
        task = create_task_bonsai_stop_command(task, port=7112)  # record_mic
    if task.name == "_iblrig_tasks_ephysChoiceWorld":
        task = create_task_create_command(task, poop=False)
    if task.name == "_iblrig_tasks_ephys_certification":
        task = create_task_cleanup_command(task)
        task = create_task_bpod_lights_command(task, 0, when="PRE")
        task = create_task_bpod_lights_command(task, 1, when="POST")
    if task.name == "_iblrig_tasks_passiveChoiceWorld" or task.name == "_iblrig_tasks_passiveChoiceWorldIndependent":
        task = create_task_cleanup_command(task)
        task = create_task_poop_command(task, when="POST")
        task = create_task_bonsai_stop_command(task, port=7110)  # stim
        task = create_task_bonsai_stop_command(task, port=7112)  # record_mic
        task = create_task_bpod_lights_command(task, 0, when="PRE")
        task = create_task_bpod_lights_command(task, 1, when="POST")
        task = create_task_move_passive_command(task, when="POST")

    p.save(iblproject_path)
    print("    Task configured")


def create_ibl_tasks(iblproject_path):  # XXX: THIS!
    task_names = [
        "_iblrig_calibration_screen",
        "_iblrig_calibration_water",
        "_iblrig_calibration_input_listner",
        "_iblrig_calibration_frame2TTL",
        "_iblrig_misc_flush_water",
        "_iblrig_misc_bpod_ttl_test",
        "_iblrig_misc_frame2TTL_freq_test",
        "_iblrig_tasks_biasedChoiceWorld",
        "_iblrig_tasks_habituationChoiceWorld",
        "_iblrig_tasks_trainingChoiceWorld",
        "_iblrig_tasks_ephysChoiceWorld",
        "_iblrig_tasks_ephys_certification",
        "_iblrig_tasks_passiveChoiceWorld",
        "_iblrig_tasks_passiveChoiceWorldIndependent"
    ]
    for task_name in task_names:
        create_task(iblproject_path, task_name=task_name)
        config_task(iblproject_path, task_name=task_name)


def create_experiment(iblproject_path, exp_name: str):
    p = Project()
    p.load(iblproject_path)
    exp = p.create_experiment()
    exp.name = exp_name
    p.save(iblproject_path)
    print(f"Created experiment: {exp.name}")


def create_ibl_experiments(iblproject_path):
    experiment_names = [
        "_iblrig_calibration",
        "_iblrig_misc",
        "_iblrig_tasks",
    ]
    for exp_name in experiment_names:
        create_experiment(iblproject_path, exp_name=exp_name)


def create_setup(exp, setup_name: str, board: str, subj: object, task: str = None):
    # task name is defined as the experiment_name + '_' + setup_name
    # Create or get preexisting setup
    setup = exp.create_setup()

    setup.name = setup_name
    setup.task = task if isinstance(task, str) else exp.name + "_" + setup_name
    setup.board = board
    setup += subj
    setup.detached = True
    print(f"    Created setup: {setup.name} for experiment {exp.name}")

    return setup


def create_experiment_setups(iblproject_path, exp_name: str):  # XXX:THIS!
    p = Project()
    p.load(iblproject_path)
    exp = [e for e in p.experiments if e.name == exp_name]
    calib_subj = [s for s in p.subjects if s.name == "_iblrig_calibration"][0]
    test_subj = [s for s in p.subjects if s.name == "_iblrig_test_mouse"][0]
    if not exp:
        raise KeyError(f"Experiment {exp} not found")
    else:
        exp = exp[0]

    if exp.name == "_iblrig_calibration":
        screen = create_setup(exp, "screen", p.boards[0].name, calib_subj)  # noqa
        water = create_setup(exp, "water", p.boards[0].name, calib_subj)  # noqa
        input_listner = create_setup(exp, "input_listner", p.boards[0].name, calib_subj)  # noqa
        frame2TTL = create_setup(exp, "frame2TTL", p.boards[0].name, calib_subj)  # noqa

    if exp.name == "_iblrig_misc":
        flush_water = create_setup(exp, "flush_water", p.boards[0].name, test_subj)  # noqa
        bpod_ttl_test = create_setup(exp, "bpod_ttl_test", p.boards[0].name, test_subj)  # noqa
        frame2TTL_freq_test = create_setup(  # noqa
            exp, "frame2TTL_freq_test", p.boards[0].name, test_subj
        )

    if exp.name == "_iblrig_tasks":
        biasedChoiceWorld = create_setup(exp, "biasedChoiceWorld", p.boards[0].name, None)  # noqa
        habituationChoiceWorld = create_setup(  # noqa
            exp, "habituationChoiceWorld", p.boards[0].name, None
        )
        trainingChoiceWorld = create_setup(  # noqa
            exp, "trainingChoiceWorld", p.boards[0].name, None
        )
        ephys_certification = create_setup(  # noqa
            exp, "ephys_certification", p.boards[0].name, None
        )
        ephysChoiceWorld = create_setup(  # noqa
            exp,
            "ephysChoiceWorld_testing",
            p.boards[0].name,
            test_subj,
            task="_iblrig_tasks_ephysChoiceWorld",
        )
        passiveChoiceWorld = create_setup(  # noqa
            exp,
            "passiveChoiceWorld_testing",
            p.boards[0].name,
            test_subj,
            task="_iblrig_tasks_passiveChoiceWorld",
        )
        passiveChoiceWorldIndependent = create_setup(  # noqa
            exp,
            "passiveChoiceWorldIndependent",
            p.boards[0].name,
            test_subj,
            task="_iblrig_tasks_passiveChoiceWorldIndependent",
        )

    p.save(iblproject_path)


def create_ibl_setups(iblproject_path):
    experiment_names = [
        "_iblrig_calibration",
        "_iblrig_misc",
        "_iblrig_tasks",
    ]
    for exp_name in experiment_names:
        print(f"  Creating setups for experiment <{exp_name}>")
        create_experiment_setups(iblproject_path, exp_name=exp_name)
    print("Done")


def copy_task_files(iblrig_params_path, exclude_filename=None):
    """Copy all files in root tasks folder to iblrig_params_path
    Copy all *.py files in iblrig_path to iblrig_params/IBL/tasks/<task_name>/*
    """

    iblrig_params_path = Path(iblrig_params_path)
    iblrig_params_tasks_path = iblrig_params_path / "IBL" / "tasks"
    iblrig_path = iblrig_params_path.parent / "iblrig"
    iblrig_tasks_path = iblrig_path / "tasks"
    print(f"\nCopying task files to {iblrig_params_tasks_path}")

    if exclude_filename is None:
        exclude_filename = "random_stuff"

    def copy_files(src_folder, dst_folder, glob="*", exclude_filename=exclude_filename):
        src_folder = Path(src_folder)
        dst_folder = Path(dst_folder)
        src_list = [
            x for x in src_folder.glob(glob) if x.is_file() and exclude_filename not in str(x)
        ]
        for f in src_list:
            shutil.copy(f, dst_folder)
            print(f"  Copied {f} to {dst_folder}")

    # Copy all tasks
    tasks = [x for x in iblrig_tasks_path.glob("*") if x.is_dir() and x.name != "__pycache__"]
    for sf in tasks:
        df = iblrig_params_tasks_path / sf.name
        df.mkdir(parents=True, exist_ok=True)
        copy_files(sf, df)
    print("Done")


def setups_to_remove(iblproject_path):
    p = Project()
    p.load(iblproject_path)
    exp = [e for e in p.experiments if e.name == "_iblrig_calibration"]
    if not exp:
        raise KeyError(f"Experiment {exp} not found")
    else:
        exp = exp[0]
        setup = [s for s in exp.setups if s.name == "screen"]
        if not setup:
            print(f"Setup {setup} not found")
        else:
            setup = setup[0]
            print()
            exp -= setup
            p.save(iblproject_path)


def main(iblrig_params_path):
    """for update to 5.1.0+
    Change location of all post scripts to iblrig/scripts
    and removeall files in iblrig_params except user_settings.
    """
    # Set pathes and create dir
    iblrig_params_path = Path(iblrig_params_path)
    iblproject_path = iblrig_params_path / "IBL"
    os.makedirs(iblrig_params_path, exist_ok=True)
    os.makedirs(Path(iblrig_params_path / "plugins"), exist_ok=True)

    delete_untracked_files(iblrig_params_path)
    copy_pybpod_user_settings()

    create_ibl_project(iblproject_path)
    create_ibl_board(iblproject_path)
    create_ibl_subjects(iblproject_path)
    create_ibl_users(iblproject_path)
    create_ibl_tasks(iblproject_path)
    create_ibl_experiments(iblproject_path)
    create_ibl_setups(iblproject_path)

    copy_task_files(iblrig_params_path)

    setups_to_remove(iblproject_path)
    return


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print(f"No argument given, setting default values...\nIBLRIG_FOLDER - {IBLRIG_FOLDER}\nIBLRIG_PARAMS_FOLDER - "
              f"{IBLRIG_PARAMS_FOLDER}")
        main(IBLRIG_PARAMS_FOLDER)
    elif len(sys.argv) == 2:
        print(f"\nSetting up PyBpod IBL project to folder: {sys.argv[1]}")
        main(sys.argv[1])
    print("setup_pybpod.py completed")
