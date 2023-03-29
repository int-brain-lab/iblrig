## How to develop on this repository 
This repository is adhering to the following conventions:
* [semantic versioning](https://semver.org/) for consistent version numbering logic
* [gitflow](https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow) for managing branches 
* [flake8](https://flake8.pycqa.org/) for style guide enforcement 

![](README_semver.png)
![](README_gitflow_workflow.png)

Please review these conventions to more easily contribute to the project.

### New feature branches:
- a `new_feature` branch is forked from the current `develop` branch
- the `new_feature` branch is then merged back into the `develop` branch
- the `new_feature` branch will eventually be deleted

### Release candidate branches:
- a release candidate, `rc` branch is a "pre-release" branch for beta testers on production rigs
- the `rc` branch is forked from the `develop` branch
- once the `rc` has been thoroughly tested, it will be merged into `master` and `develop`
- the `rc` branch will eventually be deleted

### Hotfix branches:
- a `hotfix` or `maintenance` branch is forked from `master`
- once the fix has been thoroughly tested, it will get merged back into `master` and `develop`
- the `hotfix` branch will eventually be deleted

#### Install Python v3.8 and set up venv for iblrig on Ubuntu 22.04

Instructions are for the assumption that this is for development and that the desired directory to work out of is 
`~/Documents/repos/iblrig`

Installing from deadsnakes repo:
```bash
sudo apt install build-essential --yes
sudo add-apt-repository ppa:deadsnakes/ppa --yes
sudo apt update --yes && sudo apt upgrade --yes
sudo apt install python3.8 python3.8-dev python3.8-venv python3.8-tk --yes
python3.8 -m ensurepip --default-pip --user
python3.8 -m pip install --upgrade pip --user
```

Testing python3.8 venv functionality:
```bash
python3.8 -m venv test_venv
source test_venv/bin/activate
python --version
which python
python -m pip install --upgrade pip wheel
deactivate
rm -rf test_venv
```

#### Install required library for running unit tests on Ubuntu 22.04

PortAudio library is required for the `sounddevice` python package. It can be installed with the following commands
```bash
sudo apt update && sudo apt install -y libportaudio2
```

---

### Troubleshooting Notes

#### Anaconda (base) environment in Powershell
When launching powershell to run any rig code, it is not recommended to have the anaconda base environment active. Run the 
following commands to deactivate the base environment and disable it from auto-activating in the future:    
```powershell
conda deactivate
conda config --set auto_activate_base false
```

#### Windows
Disable Microsoft Store associations with `python` command
* Open the Settings or Start menu and search for “App execution aliases” or “Manage app execution aliases” 
* Disable any python entries listed

#### Stim display on wrong screen
If the visual stimulus appears on the wrong screen:
* short term, pressing `F11` on the keyboard will unmaximize the window; allowing movement of the stimulus to the correct screen 
* longer term, take note of a file called `C:\iblrig_params\.iblrig_params.json`; within that file is a variable called 
`DISPLAY_IDX`, its value will be set to 0 or 1. If the stimulus screen initially launches on the wrong monitor (PC screen instead 
of iPad screen), then change the value of `DISPLAY_IDX`. Change it to 0 if it was on 1, change it to 1 if it was on 0.
  * Please note, the display index value is something assigned by OS and could potentially change between reboots

#### pybpod custom tasks from v6 not running after migrating to v7
After migrating to v7 of the iblrig software, some may encounter a `ModuleNotFoundError: No module named 'iblrig'` error when 
attempting to run their custom tasks. This has to do with the way that pybpod calls python in the pre and post commands. Within 
the `C:\iblrig_params\custom_path\tasks\my_custom_task\` directory, there should be a `my_custom_task.json` file. If this file 
contains any calls to a specific python executable, they must be updated to `C:\iblrig\venv\Scripts\python`.