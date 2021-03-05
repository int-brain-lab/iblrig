import shutil
import sys
from pathlib import Path
from iblrig.alyx import check_alyx_ok
from pybpodgui_api.models.project import Project

IBLRIG_FOLDER = Path(__file__).absolute().parent
IBLRIG_PARAMS_FOLDER = IBLRIG_FOLDER.parent / "iblrig_params"

print(IBLRIG_FOLDER, "\n", IBLRIG_PARAMS_FOLDER)


def check_project_name_ok(name):
    if check_alyx_ok():
        from oneibl.one import ONE
        one = ONE()
        all_projects = [x['name'] for x in one.alyx.rest('projects', 'list')]
        return True if name in all_projects else False
    else:
        print("Cannot check project names with alyx.")
        return



def create_project(name):
    project_path = IBLRIG_PARAMS_FOLDER / name

    p = Project()
    print(f"Creating project: {name}")
    try:
        p.load(project_path)
        print(f"  Skipping creation: project {name} found in: {project_path}")
    except:  # noqa
        p.name = name
        p.save(project_path)
        print(f"  Project created: {name}")
