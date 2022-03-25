#!/usr/bin/env python
# @File: iblone/ibllib_calls.py
# @Author: Niccolo' Bonacchi (@nbonacchi)
# @Date: Tuesday, March 22nd 2022, 9:54:59 am
import os
import subprocess
from iblrig import envs
from pathlib import Path


class ONERunner:
    ibllib_env = Path(envs.get_env_python(env_name="ibllib")).parent
    one = None

    @classmethod
    def __new__(cls, one: str = None):
        cls.one = one
        return cls

    @classmethod
    def _command_builder(
        cls, comm: str, ret: str = "[print(x) for x in resp]"
    ):
        if cls.one is None:
            onecall = "ONE()"
        elif cls.one == 'test':
            onecall = "".join([
                "ONE(base_url='https://test.alyx.internationalbrainlab.org',",
                "username='test_user',password='TapetesBloc18')"])

        command = "\n".join(
            [
                "from one.api import ONE",
                "try:",
                f"    one = {onecall}",
                "except:",
                "    pass",
                f"resp = {comm}",
                ret
            ]
        )
        return command

    @classmethod
    def _command_runner(cls, command: str):
        subresp = subprocess.run(
            f'python -c "{command}"',
            env=dict(os.environ.copy(), PATH=cls.ibllib_env),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
        )
        return subresp.stdout.decode().split()

    @classmethod
    def get_all_project_names(cls):
        proj_names = "[x['name'] for x in one.alyx.rest('projects', 'list')]"
        command = cls._command_builder(proj_names)
        resp = cls._command_runner(command)
        return resp

    @classmethod
    def get_all_user_names(cls):
        user_names = "[x['username'] for x in one.alyx.rest('users', 'list')]"
        command = cls._command_builder(user_names)
        resp = cls._command_runner(command)
        return resp

    @classmethod
    def get_subject_name(cls, subj):
        command_str = f"one.alyx.rest('subjects', 'list', nickname='{subj}')"
        command_ret = "print(resp)"
        command = cls._command_builder(command_str, ret=command_ret)
        resp = cls._command_runner(command)
        return resp

    @classmethod
    def get_all_subject_from_project(cls, project_name: str):
        command_str = f"list(one.alyx.rest('subjects', 'list', project={project_name}))"
        command = cls._command_builder(command_str)
        resp = cls._command_runner(command)
        return resp

    @classmethod
    def get_one_user(cls):
        command_str = "one.alyx.authenticate()"
        command_ret = "print(one.alyx.user)"
        command = cls._command_builder(command_str, ret=command_ret)
        resp = cls._command_runner(command)
        return resp

    @classmethod
    def get_project_users(cls, proj):
        command_str = f"one.alyx.rest('projects', 'read', id='{proj}')['users']"
        command = cls._command_builder(command_str)
        resp = cls._command_runner(command)
        return resp


print(ONERunner.one)  #  = 'test'
# ONERunner.get_all_subject_from_project("ibl_mainenlab")

# ONERunner.get_project_users("ibl_mainenlab")
# ONERunner.get_all_project_names()

# get_project_names = ";".join(
#     [
#         "from one.api import ONE",
#         "one = ONE()",
#         "project_names = [x['name'] for x in one.alyx.rest('projects', 'list')]",
#         "[print(x) for x in project_names]",
#     ]
# )

# project_names = subprocess.run(
#     f'python -c "{get_project_names}"',
#     env=dict(os.environ.copy(), PATH=ibllib_env),
#     stdout=subprocess.PIPE,
#     stderr=subprocess.PIPE,
#     shell=True,
# )

# projects = project_names.stdout.decode().split()

# ------------------------------------------------- #

# get_user_names = ";".join(
#     [
#         "from one.api import ONE",
#         "one = ONE()",
#         "user_names = [x['username'] for x in one.alyx.rest('users', 'list')]",
#         "[print(x) for x in user_names]",
#     ]
# )

# user_names = subprocess.run(
#     f'python -c "{get_user_names}"',
#     env=dict(os.environ.copy(), PATH=ibllib_env),
#     stdout=subprocess.PIPE,
#     stderr=subprocess.PIPE,
#     shell=True,
# )

# users = user_names.stdout.decode().split()

# ------------------------------------------------- #

# subj = "ZFM-04022_DELETE_ME"
# get_subject_name = ";".join(
#     [
#         "from one.api import ONE",
#         "one = ONE()",
#         f"resp = one.alyx.rest('subjects', 'list', nickname='{subj}')",
#         "print(resp)",
#     ]
# )

# subj_name = subprocess.run(
#     f'python -c "{get_subject_name}"',
#     env=dict(os.environ.copy(), PATH=ibllib_env),
#     stdout=subprocess.PIPE,
#     stderr=subprocess.PIPE,
#     shell=True,
# )

# subject = subj_name.stdout.decode().split()

# ------------------------------------------------- #

# get_one_user = ""
# get_one_user_resp = "print(one.alyx.user)"


# get_project_users = "one.alyx.rest('projects', 'read', id=project_name)['users']"
