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
    def _command_builder(cls, comm: str, ret: str = "[print(x) for x in resp]"):
        if cls.one is None:
            onecall = "ONE()"
        elif cls.one == "test":
            onecall = "".join(
                [
                    "ONE(base_url='https://test.alyx.internationalbrainlab.org',",
                    "username='test_user',password='TapetesBloc18')",
                ]
            )

        command = "\n".join(
            [
                "from one.api import ONE",
                "try:",
                f"    one = {onecall}",
                "except:",
                "    print('Cannot instantiate ONE client')",
                f"resp = {comm}",
                ret,
            ]
        )
        return command

    @classmethod
    def _command_runner(
        cls, command: str, strip: bool = True, split: bool = True, parse: bool = False
    ):
        subresp = subprocess.run(
            f'python -c "{command}"',
            env=dict(os.environ.copy(), PATH=cls.ibllib_env),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
        )
        out = subresp.stdout.decode()
        if strip:
            out = out.strip()
        if split:
            out = out.split()
        if parse:
            out = eval(out)
        if not out:
            return
        return out[0] if len(out) == 1 else out

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
    def get_all_subjects_from_project(cls, project_name: str):
        command_str = f"list(one.alyx.rest('subjects', 'list', project='{project_name}'))"
        command_ret = "print([x for x in resp])"
        command = cls._command_builder(command_str, ret=command_ret)
        resp = cls._command_runner(command, split=False, parse=True)
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


print(ONERunner.one)  # = 'test'
