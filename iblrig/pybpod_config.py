"""
Create files on disk for user defined projects registered on alyx.
Will create a new project with users and subjects from Alyx info
Creates project if exists on Alyx
Create default rig subjects and all subjects associated to the project_name
Create default user and currently logged in user (uses ONE params ALYX_USER)

Usage:
  CLI in ./scripts
    python create_custom_project_from_alyx.py [project_name]


Local pybpod functions (used in setup_default config):
    create_project
    create_user
    create_subject


Alyx dependent functions:
    create_alyx_project
    create_ONE_alyx_user
    create_local_subjects_from_alyx

Return: None or json dict
"""
import json
from pathlib import Path

from one.api import ONE
from pybpodgui_api.models.project import Project

import iblrig.path_helper as ph

IBLRIG_PARAMS_FOLDER = Path(ph.get_iblrig_params_folder())

print(ph.get_iblrig_folder(), "\n", IBLRIG_PARAMS_FOLDER)

local2alyx_names = {"IBL": "ibl_neuropixel_brainwide_01"}
alyx2local_names = {"ibl_neuropixel_brainwide_01": "IBL"}

# UTILS
def _load_pybpod_obj_json(obj):
    objpath = Path(obj.path).joinpath(obj.name + ".json")
    with open(objpath, "r") as f:
        out = json.load(f)

    return out


def _save_pybpod_obj_json(obj, data):
    objpath = Path(obj.path).joinpath(obj.name + ".json")
    with open(objpath, "w") as f:
        json.dump(data, f, indent=2)

    return


def _update_pybpod_obj_json(obj, patch: dict):
    objdict = _load_pybpod_obj_json(obj)
    print(f"Updating local subject [{obj.name}]'s json record with alyx subject info")
    objdict.update(patch)
    _save_pybpod_obj_json(obj, objdict)

    return objdict


def alyx_project_exists(project_name, one=None):
    project_name = local2alyx_names.get(project_name, project_name)
    one = one or ONE()
    print(f"Checking existence of project [{project_name}] on Alyx")
    all_projects_names = [x["name"] for x in one.alyx.rest("projects", "list")]
    if project_name not in all_projects_names:
        print(f"Project [{project_name}] not found on Alyx")
        out = False
    else:
        out = True

    return out


def alyx_user_exists(name, one=None):
    one = one or ONE()
    print(f"Checking existence of user [{name}] on Alyx")
    all_user_names = [x["username"] for x in one.alyx.rest("users", "list")]
    if name not in all_user_names:
        print(f"User [{name}] not found on Alyx")
        out = False
    else:
        out = True

    return out


def alyx_subject_exists(name, one=None):
    one = one or ONE()
    print(f"Checking existence of subject [{name}] on Alyx")
    resp = one.alyx.rest("subjects", "list", nickname=name)
    if not resp:
        print(f"Subject [{name}] not found on Alyx")
        out = False
    else:
        out = True

    return out


# PROJECT
def pybpod_project_exists(project_name):
    project_name = alyx2local_names.get(project_name, project_name)
    project_path = IBLRIG_PARAMS_FOLDER / project_name
    p = Project()
    project_exists = None
    try:
        print(f"Checking existence of project [{project_name}] locally")
        p.load(project_path)
        project_exists = True
    except:  # noqa
        print(f"Project not found: [{project_path}]")
        project_exists = False

    return project_exists


def create_project(project_name, force=False):
    project_name = alyx2local_names.get(project_name, project_name)
    project_path = IBLRIG_PARAMS_FOLDER / project_name
    p = Project()
    if force or not pybpod_project_exists(project_name):
        p.name = project_name
        p.save(project_path)
        print(f"  Project created: [{project_name}]")
    else:
        print(f"  Skipping creation: project [{project_name}] found in: [{project_path}]")
        p = Project()
        p.load(project_path)
    return p


def create_local_project_from_alyx(project_name, one=None, force=False):
    project_name = local2alyx_names.get(project_name, project_name)
    one = one or ONE()
    if force or alyx_project_exists(project_name, one=one):
        p = create_project(project_name, force=force)
        out = _load_pybpod_obj_json(p)
    else:
        out = None

    return out


# SUBJECTS
def create_subject(project_name, subject_name: str, force=False):
    project_name = alyx2local_names.get(project_name, project_name)
    project_path = IBLRIG_PARAMS_FOLDER / project_name
    p = Project()
    print(f"Loading [{project_path}]")
    p.load(project_path)
    subject = p.find_subject(subject_name)
    if force or subject is None:
        subject = p.create_subject()
        subject.name = subject_name
        p.save(project_path)
        print(f"  Created subject: [{subject_name}]")
    # Create default subjects for project {project_name} if they don't exist
    if p.find_subject("_iblrig_test_mouse") is None:
        create_subject(project_name, subject_name="_iblrig_test_mouse", force=True)
    if p.find_subject("_iblrig_calibration") is None:
        create_subject(project_name, subject_name="_iblrig_calibration", force=True)

    return subject


def _get_alyx_subjects(project_name, one=None):
    project_name = local2alyx_names.get(project_name, project_name)
    if not alyx_project_exists(project_name, one=one):
        return []
    one = one or ONE()
    all_proj_subs = list(one.alyx.rest("subjects", "list", project=project_name))

    return all_proj_subs


def _create_and_patch_subject(project_name, asub, force=False):
    """creates local subject subject and patches pybpod json obj using asub data from alyx subject
    returns patched dict of pybpod json object"""
    project_name = alyx2local_names.get(project_name, project_name)
    s = create_subject(project_name, asub["nickname"], force=force)
    sdict = _update_pybpod_obj_json(s, asub)

    return sdict


def create_local_subjects_from_alyx_project(project_name, one=None, force=False):
    project_name = alyx2local_names.get(project_name, project_name)
    alyx_subjects = _get_alyx_subjects(project_name, one=one)
    print(f"Creating [{len(alyx_subjects)}] subjects for project [{project_name}]")
    patched_subjects = []
    for asub in alyx_subjects:
        patched_subjects.append(_create_and_patch_subject(project_name, asub, force=force))

    return patched_subjects


# USERS
def create_user(project_name, username="_iblrig_test_user", force=False):
    project_name = alyx2local_names.get(project_name, project_name)
    project_path = IBLRIG_PARAMS_FOLDER / project_name
    p = Project()
    print(f"Loading [{project_path}]")
    if not pybpod_project_exists(project_name):
        return

    p.load(project_path)
    if force or p.find_user(username) is None:
        user = p.create_user()
        user.name = username
        p.save(project_path)
        print(f"  Created user: [{user.name}] in project [{project_name}]")
    else:
        user = p.find_user(username)
        print(
            f"  Skipping creation: User [{user.name}] already exists in project [{project_name}]"
        )

    if p.find_user("_iblrig_test_user") is None:
        create_user(project_name, username="_iblrig_test_user", force=True)

    return user


def create_ONE_alyx_user(project_name, one=None, force=False):
    project_name = local2alyx_names.get(project_name, project_name)
    one = one or ONE()
    out = None
    uname = one.alyx.user
    if not alyx_user_exists(uname, one=one):
        return

    user = create_user(project_name, username=uname, force=force)
    if user:
        out = _load_pybpod_obj_json(user)

    return out


def create_local_users_from_alyx_project(project_name, one=None, force=False) -> None:
    project_name = local2alyx_names.get(project_name, project_name)
    one = one or ONE()
    try:
        unames = one.alyx.rest("projects", "read", id=project_name)["users"]
        for u in unames:
            create_user(project_name, username=u, force=force)
    except:  # noqa
        print(f"No project found on alyx with name [{project_name}]")


def create_custom_project_from_alyx(project_name, one=None, force=False) -> None:
    project_name = local2alyx_names.get(project_name, project_name)
    one = one or ONE()
    create_local_project_from_alyx(project_name, one=one, force=force)
    create_local_subjects_from_alyx_project(project_name, one=one, force=force)
    create_local_users_from_alyx_project(project_name, one=one, force=force)
    create_board_from_main_project_to(project_name, force=False)


# BOARD (requires one board per rig)
def create_board_from_main_project_to(project_name, force=False):
    project_name = alyx2local_names.get(project_name, project_name)
    if project_name == "IBL":
        print("Can't create board of main project")
        return
    project_path = IBLRIG_PARAMS_FOLDER / project_name
    iblproj = Project()
    iblproj.load(IBLRIG_PARAMS_FOLDER / "IBL")
    print("Looking for boards in default project")
    if not iblproj.boards or len(iblproj.boards) > 1:
        print(f"0 or 2+ boards found in main project: {[x.name for x in iblproj.boards]}")
        return

    bname = iblproj.boards[0].name
    print("Board found: [{}]".format(bname))
    p = Project()
    if not pybpod_project_exists(project_name):
        return

    print(f"Loading [{project_path}]")
    p.load(project_path)
    if force or not p.boards:
        board = p.create_board()
        board.name = iblproj.boards[0].name
        p.save(project_path)
        print(f"  Created board: [{board.name}] in project [{project_name}]")
    elif len(p.boards) > 1:
        print(
            f"  Skipping creation: project [{project_name}] already has [{len(p.boards)}] boards"
        )
    elif len(p.boards) == 1:
        bname = p.boards[0].name
        print(f"  Skipping creation: Board [{bname}] already exists in project [{project_name}]")

    return


if __name__ == "__main__":
    pass
