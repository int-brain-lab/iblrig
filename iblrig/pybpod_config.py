import json
import shutil
import sys
from pathlib import Path

from iblrig.alyx import check_alyx_ok
from oneibl.one import ONE
from pybpodgui_api.models.project import Project

IBLRIG_FOLDER = Path(__file__).absolute().parent
IBLRIG_PARAMS_FOLDER = IBLRIG_FOLDER.parent / "iblrig_params"

print(IBLRIG_FOLDER, "\n", IBLRIG_PARAMS_FOLDER)


def check_project_name_ok(name, one=None):
    if one is None:
        one = ONE()
    if check_alyx_ok():
        all_projects = [x["name"] for x in one.alyx.rest("projects", "list")]
        print(f"Checking existance of project {name} on Alyx")
        return True if name in all_projects else False
    else:
        print("Cannot check project names with alyx.")
        return


def create_project(name, one=None, force=False):
    if one is None:
        one = ONE()
    if force or check_project_name_ok(name, one=one):
        project_path = IBLRIG_PARAMS_FOLDER / name
        p = Project()
        print(f"Checking existance of project {name} locally")
        try:
            p.load(project_path)
            print(f"  Skipping creation: project {name} found in: {project_path}")
        except:  # noqa
            p.name = name
            p.save(project_path)
            print(f"  Project created: {name}")
            return p


def create_subject(project_path, subject_name: str, force=False):
    p = Project()
    p.load(project_path)
    subject = p.find_subject(subject_name)
    if force or subject is None:
        subject = p.create_subject()
        subject.name = subject_name
        p.save(project_path)
        print(f"  Created subject: {subject_name}")
    return subject


def _get_alyx_subjects(project_name, one=None):
    if one is None:
        one = ONE()
    if not check_project_name_ok(project_name, one=one):
        print(f"Project {project_name} not found on Alyx")
        return
    all_usr_subs = list(one.alyx.rest("subjects", "list", project=project_name))
    subs = [x for x in all_usr_subs if project_name in x["projects"]]
    return subs


def _create_alyx_subject(project_path, asub, one=None):
    if one is None:
        one = ONE()
    s = create_subject(project_path, asub["nickname"])
    fpath = Path(s.path).joinpath(Path(s.path).name + ".json")
    sdict = json.load(open(fpath, "r"))
    sdict.update(asub)
    json.dump(sdict, open(fpath, "w"), indent=2)
    print(f"Added, alyx info to local subject {sdict['nickname']}")
    return sdict


def create_alyx_subjects(project_path, one=None):
    if one is None:
        one = ONE()
    project_name = Path(project_path).name
    alyx_subjects = _get_alyx_subjects(project_name, one=one)
    print(f"Creating {len(alyx_subjects)} subjects for project {project_name}")
    for asub in alyx_subjects:
        sdict = _create_alyx_subject(project_path, asub)
    print(f"Creating default subjects for project {project_name}")
    create_subject(project_path, subject_name="_iblrig_test_mouse")
    create_subject(project_path, subject_name="_iblrig_calibration")


def create_user(project_path, username="_iblrig_test_user", force=False):
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
        create_user(project_path, username="_iblrig_test_user", force=True)


if __name__ == "__main__":
    IBLRIG_FOLDER = Path(__name__).absolute().parent
    IBLRIG_PARAMS_FOLDER = IBLRIG_FOLDER.parent / "iblrig_params"
    project_name = "bla"
    project_path = IBLRIG_PARAMS_FOLDER / project_name

    one = ONE()
    p = create_project(project_name, one=one)
    create_user(p.path, username=one._par.ALYX_LOGIN)
    create_alyx_subjects(p.path, one=one)
