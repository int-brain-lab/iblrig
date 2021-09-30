#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @File: iblrig/git.py
# @Author: Niccolo' Bonacchi (@nbonacchi)
# @Date: Friday, July 16th 2021, 12:57:29 pm
import subprocess
from packaging.version import parse


def get_versions(verbose=False, only_available=False):
    vers = subprocess.check_output(["git", "ls-remote", "--tags", "origin"]).decode().split()
    vers = [x for x in vers[1::2] if "{" not in x]
    vers = [x.split("/")[-1] for x in vers]
    broken = ["6.3.0", "6.3.1"]
    available = [x for x in vers if parse(x) >= parse("6.2.5") and x not in broken]
    if verbose:
        print("Available versions: {}".format(available))
    return available if only_available else vers


def get_branches(verbose=False):
    branches = subprocess.check_output(["git", "ls-remote", "--heads", "origin"]).decode().split()
    branches = [x.split("heads")[-1] for x in branches[1::2]]
    branches = [x[1:] for x in branches]
    if verbose:
        print("Available branches: {}".format(branches))

    return branches


def get_current_branch(verbose=False):
    branch = (
        subprocess.check_output(["git", "branch", "--points-at", "HEAD"])
        .decode()
        .strip()
        .strip("* ")
    )
    if verbose:
        print("Current branch: {}".format(branch))
    return branch


def get_current_version(verbose=False):
    tag = subprocess.check_output(["git", "tag", "--points-at", "HEAD"]).decode().strip()
    if verbose:
        print("Current version: {}".format(tag))
    return tag


def pull(branch):
    subprocess.call(["git", "pull", "origin", branch, "-q"])


def fetch():
    subprocess.call(["git", "fetch", "--all", "-q"])


def checkout_version(ver):
    print("\nChecking out {}".format(ver))
    subprocess.call(["git", "reset", "--hard", "-q"])
    subprocess.call(["git", "checkout", "tags/" + ver, "-q"])
    pull(f"tags/{ver}")


def checkout_branch(branch):
    print("\nChecking out {}".format(branch))
    subprocess.call(["git", "reset", "--hard", "-q"])
    subprocess.call(["git", "checkout", branch, "-q"])
    pull(branch)


def checkout_single_file(file=None, branch="master"):
    print("Checking out", file, "from branch", branch)
    subprocess.call("git checkout origin/{} -- {}".format(branch, file).split())


def update_remotes():
    subprocess.call(["git", "remote", "update"])


def branch_info():
    print("Current availiable branches:")
    print(subprocess.check_output(["git", "branch", "-avv"]).decode())


if __name__ == "__main__":
    pass
