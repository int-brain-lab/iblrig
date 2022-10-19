import json
from pathlib import Path

from one.api import ONE

from scripts.ibllib import alyx

ROOT_FOLDER = Path().home().joinpath("TempAlyxProjectData")
ROOT_FOLDER.mkdir(parents=True, exist_ok=True)


def check_alyx_data() -> bool:
    files = [x for x in ROOT_FOLDER.glob("*") if x.suffix == ".json"]
    return True if files else False


def load_json_data(json_filename: str) -> object:
    with open(json_filename, "r") as f:
        json_data = json.load(f)
    return json_data


def get_all_project_names() -> list:
    projects = load_json_data(ROOT_FOLDER.joinpath("projects.json"))
    return [x["name"] for x in projects]


def get_all_user_names() -> list:
    users = load_json_data(ROOT_FOLDER.joinpath("users.json"))
    return [x["username"] for x in users]


def get_project_users(project_name: str) -> list:
    projects = load_json_data(ROOT_FOLDER.joinpath("projects.json"))
    proj = [x for x in projects if x["name"] == project_name]
    if proj:
        users = proj[0]["users"]
    else:
        users = []

    return users


def get_all_subjects_from_project(project_name: str) -> list:
    subjects_path = [x for x in ROOT_FOLDER.glob("*") if project_name in x.name and "json" in x.suffix]

    if not subjects_path:
        print(f"Project {project_name} not found")
        return []
    elif len(subjects_path) > 1:
        print(f"More than one subjects file found for project {project_name}")
        return []

    subjects = load_json_data(subjects_path[0])

    return subjects


def get_one_user():
    user_file = next(ROOT_FOLDER.glob("*.oneuser"), None)
    if user_file is not None:
        return user_file.stem


def call_one_get_project_data(project_name: str, lab: str = None, one_test: bool = False):
    if one_test:
        one = ONE(
            base_url="https://test.alyx.internationalbrainlab.org",
            username="test_user",
            password="TapetesBloc18",
        )
    else:
        one = ONE()
    alyx.get_alyx_project_info(project_name=project_name, lab=lab, one=one)


def call_one_sync_params(one_test: bool = False):
    if one_test:
        one = ONE(
            base_url="https://test.alyx.internationalbrainlab.org",
            username="test_user",
            password="TapetesBloc18",
        )
    else:
        one = ONE()
    alyx.sync_local_params_to_alyx(one=one)
