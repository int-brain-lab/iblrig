"""
Create files on disk for user defined projects registered on alyx.
Will create a new project with users and subjects from Alyx info
Creates project if exists on Alyx
Create default rig subjects and all subjects associated to the project_name
Create default user and currently logged in user (uses ONE params ALYX_USER)

Usage:
    python pybpod_config.py <project_name>


Local pybpod functions (used in setup_default config):
    create_project
    create_user
    create_subject


Alyx dependent functions:
    create_alyx_project
    create_alyx_user
    create_alyx_subjects

Return: None or json dict
"""
import json
from pathlib import Path

import iblrig.path_helper as ph
from oneibl.one import ONE
from pybpodgui_api.models.project import Project

IBLRIG_PARAMS_FOLDER = Path(ph.get_iblrig_params_folder())

print(ph.get_iblrig_folder(), "\n", IBLRIG_PARAMS_FOLDER)


# UTILS
def _load_pybpod_obj_json(obj):
    objpath = Path(obj.path).joinpath(obj.name + ".json")
    return json.load(open(objpath, 'r'))


def _save_pybpod_obj_json(obj, data):
    objpath = Path(obj.path).joinpath(obj.name + ".json")
    json.dump(data, open(objpath, "w"), indent=2)
    return


def _update_pybpod_obj_json(obj, patch: dict):
    objdict = _load_pybpod_obj_json(obj)
    print(f"Updating local subject {objdict['nickname']}'s json record with alyx subject info")
    objdict.update(patch)
    _save_pybpod_obj_json(obj, objdict)

    return objdict


def alyx_project_exists(name, one=None):
    if one is None:
        one = ONE()
    print(f"Checking existence of project {name} on Alyx")
    all_projects_names = [x["name"] for x in one.alyx.rest("projects", "list")]

    return True if name in all_projects_names else False


def alyx_user_exists(name, one=None):
    if one is None:
        one = ONE()
    print(f"Checking existence of user {name} on Alyx")
    all_user_names = [x["username"] for x in one.alyx.rest('users', 'list')]
    return True if name in all_user_names else False


def alyx_subject_exists(name, one=None):
    if one is None:
        one = ONE()
    print(f"Checking existence of subject {name} on Alyx")
    resp = one.alyx.rest('subjects', 'list', nickname=name)
    return True if resp else False


# PROJECT
def pybpod_project_exists(name):
    project_path = IBLRIG_PARAMS_FOLDER / name
    p = Project()
    project_exists = None
    try:
        print(f"Checking existence of project {name} locally")
        p.load(project_path)
        project_exists = True
    except:  # noqa
        project_exists = False

    return project_exists


def create_project(name, force=False):
    project_path = IBLRIG_PARAMS_FOLDER / name
    p = Project()
    if force or not pybpod_project_exists(name):
        p.name = name
        p.save(project_path)
        print(f"  Project created: {name}")
    else:
        print(f"  Skipping creation: project {name} found in: {project_path}")

    return p


def create_alyx_project(name, one=None, force=False):
    if one is None:
        one = ONE()
    if force or alyx_project_exists(name, one=one):
        p = create_project(name, force=force)
        out = _load_pybpod_obj_json(p)
    else:
        out = None

    return out


# SUBJECTS
def create_subject(project_name, subject_name: str, force=False):
    project_path = IBLRIG_PARAMS_FOLDER / project_name
    p = Project()
    p.load(project_path)
    subject = p.find_subject(subject_name)
    if force or subject is None:
        subject = p.create_subject()
        subject.name = subject_name
        p.save(project_path)
        print(f"  Created subject: {subject_name}")
    # Create default subjects for project {project_name} if they don't exist
    if p.find_subject("_iblrig_test_user") is None:
        create_subject(project_name, subject_name="_iblrig_test_user", force=True)
    if p.find_subject("_iblrig_test_user") is None:
        create_subject(project_name, subject_name="_iblrig_calibration", force=True)

    return subject


def _get_alyx_subjects(project_name, one=None):
    if one is None:
        one = ONE()
    if not alyx_project_exists(project_name, one=one):
        print(f"Project {project_name} not found on Alyx")
        return
    all_proj_subs = list(one.alyx.rest("subjects", "list", project=project_name))

    return all_proj_subs


def _create_alyx_subject(project_name, asub, force=False):
    s = create_subject(project_name, asub["nickname"], force=force)
    sdict = _update_pybpod_obj_json(s, asub)

    return sdict


def create_alyx_subjects(project_name, one=None):
    project_path = IBLRIG_PARAMS_FOLDER / project_name
    if one is None:
        one = ONE()
    alyx_subjects = _get_alyx_subjects(project_name, one=one)
    print(f"Creating {len(alyx_subjects)} subjects for project {project_name}")
    patched_subjects = []
    for asub in alyx_subjects:
        patched_subjects.append(_create_alyx_subject(project_path, asub))

    return patched_subjects


# USERS
def create_user(project_name, username="_iblrig_test_user", force=False):
    project_path = IBLRIG_PARAMS_FOLDER / project_name
    print(f"Loading {project_path}")
    p = Project()
    p.load(project_path)
    if force or p.find_user(username) is None:
        user = p.create_user()
        user.name = username
        p.save(project_path)
        print(f"  Created user: <{user.name}>")
    else:
        user = p.find_user(username)
        print(f"  Skipping creation: User <{user.name}> already exists")

    if p.find_user("_iblrig_test_user") is None:
        create_user(project_name, username="_iblrig_test_user", force=True)

    return user


def create_alyx_user(project_name, one=None, force=False):
    if one is None:
        one = ONE()
    uname = one._par.ALYX_LOGIN
    assert alyx_user_exists(uname, one=one)
    user = create_user(project_name, username=uname, force=force)
    out = _load_pybpod_obj_json(user)

    return out


if __name__ == "__main__":
    IBLRIG_FOLDER = Path(__name__).absolute().parent
    IBLRIG_PARAMS_FOLDER = IBLRIG_FOLDER.parent / "iblrig_params"
    project_name = "bla"
    project_path = IBLRIG_PARAMS_FOLDER / project_name

    one = ONE()
    p = create_alyx_project(project_name, one=one, force=False)
    u = create_alyx_user(project_name, one=one, force=False)
    s = create_alyx_subjects(project_name, one=one,)

