#!/usr/bin/env python
# @File: scripts/sync_to_alyx.py
# @Author: Niccolo' Bonacchi (@nbonacchi)
# @Date: Thursday, May 26th 2022, 1:29:50 pm
import argparse

import iblrig.pybpod_config as pbc
from iblrig.ibllib_calls import call_one_get_project_data, get_all_subjects_from_project


def main(project: str, lab: str) -> None:
    """Substitutes the deprecated sync to alyx module of pybpod

    Args:
        project (str): The project name in pybpod to receive users and subjects
        lab (str): The labname of the subjects

    Especially for platform projects subjects are numerous, restricting by those in current lab
    Avoids downloading too much useless subject references and speeds up the query
    """
    # The project in pybpod where to add the subjects
    project_name = pbc.local2alyx_names[project]
    # Get the subjects you want to add from Alyx and save them to disk
    call_one_get_project_data(project_name, lab=lab)
    # Load all the subjects queried from Alyx
    subjects = get_all_subjects_from_project(project_name)
    # Filter for alive subjects
    alive_subjects = [x for x in subjects if x.get("alive")]
    # Create and entry in the pybpod GUI for each subject
    for asub in alive_subjects:
        pbc._create_and_patch_subject(project_name, asub)
    # Create pybpod users from Alyx users
    pbc.create_local_users_from_alyx_project(project_name)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("-p", "--project", required=True, help="The project to add subjects")
    ap.add_argument("-l", "--lab", help="The lab to query subjects", default="mainenlab")
    main(**vars(ap.parse_args()))
