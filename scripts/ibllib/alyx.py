"""
Alyx interface functions
Can do 2 things:
1. Sync params file from local to alyx
2. Download data from alyx for creating local projects from alyx projects
"""
import argparse
import json
import shutil
from pathlib import Path

from one.api import ONE

from iblrig import path_helper

ROOT_FOLDER = Path(path_helper.get_iblrig_temp_alyx_proj_folder())


def sync_local_params_to_alyx(one: object = None) -> None:
    one = one or ONE()
    local_params = _load_iblrig_params()
    _write_alyx_params(local_params, one=one)
    print("INFO: Finished syncing local params to alyx")
    return


def _load_iblrig_params() -> dict:
    """
    Loads iblrig params from default location
    """
    params_filepath = Path(path_helper.get_iblrig_params_folder()) / ".iblrig_params.json"
    if not params_filepath.exists():
        print(f"ERROR: Can't find params file: {params_filepath}")
        return {}
    with open(params_filepath, "r") as f:
        pars = json.load(f)
    return pars


def _write_alyx_params(data: dict, one: object = None) -> dict:
    one = one or ONE()
    board = data["NAME"]
    patch_dict = {"json": data}
    one.alyx.rest("locations", "partial_update", id=board, data=patch_dict)
    return data


def get_alyx_project_info(project_name: str = None, lab: str = None, one: object = None):
    """
    Returns the alyx project info for a given project name
    get all projects (has project users)
    get all users
    get project subjects
    """
    one = one or ONE()
    if not one.alyx.user:
        one.alyx.authenticate()

    ROOT_FOLDER.mkdir(parents=True, exist_ok=True)
    ROOT_FOLDER.joinpath(one.alyx.user + ".oneuser").touch()

    projects = one.alyx.rest("projects", "list")
    users = one.alyx.rest("users", "list")
    if lab is None:
        subjects = one.alyx.rest("subjects", "list", project=project_name)
    else:
        subjects = one.alyx.rest("subjects", "list", project=project_name, lab=lab)
    # Save to disk
    projects_filepath = ROOT_FOLDER.joinpath("projects.json")
    users_filepath = ROOT_FOLDER.joinpath("users.json")
    subjects_filepath = ROOT_FOLDER.joinpath(f"{project_name}_subjects.json")
    for fpath, data in zip(
        [projects_filepath, users_filepath, subjects_filepath],
        [projects, users, subjects],
    ):
        if fpath.exists():
            shutil.move(fpath, fpath.parent.joinpath(fpath.name + ".bak"))

        with open(fpath, "w") as f:
            json.dump(data, f)

        print("INFO: Saving to {}".format(fpath))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Alyx interface functions (must run in ibllib env)"
    )
    parser.add_argument(
        "--sync-params",
        required=False,
        default=False,
        action="store_true",
        help="Syncronize params file with Alyx",
    )
    parser.add_argument(
        "--get-project",
        required=False,
        default=False,
        help="Download project data from Alyx",
    )
    parser.add_argument(
        "--lab",
        required=False,
        default=None,
        help="Lab name to restrict subjects for platform projects",
    )
    parser.add_argument(
        "--one-test",
        required=False,
        default=False,
        action="store_true",
        help="Whether to use the ONE test instance (default is production)",
    )
    args = parser.parse_args()

    if args.one_test:
        one = ONE(
            base_url="https://test.alyx.internationalbrainlab.org",
            username="test_user",
            password="TapetesBloc18",
        )
    else:
        one = ONE()

    if args.sync_params:
        sync_local_params_to_alyx(one=one)
    else:
        get_alyx_project_info(one=one, project_name=args.get_project, lab=args.lab)
    print(args)
