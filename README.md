# iblrig v7
## Installation on Windows
Software has only been tested on Windows 10. No other version of Windows is supported at this time. The test user account has 
administrative rights.

### Prerequisite Software:
In order to install iblrig on a Windows machine please ensure that the following prerequisite is first installed:
- [Anaconda](https://anaconda.com)
- A fully featured text editor is recommended, something like [Notepad++](https://notepad-plus-plus.org/)

### Installation Instructions:
- Ensure Anaconda and your favorite text editor are already installed
- Ensure a stable internet connection is present as several commands will require software to be downloaded
- There is no supported upgrade path from v6 to v7
- The commands given below are assumed to be run on a 'clean' system
  - No conflicting Anaconda environment names
  - The Anaconda base environment does not have any additional packages
  - The `C:\iblrig` and `C:\iblrig_params` directories are assumed not to exist 

The following commands are to be run from the **Anaconda Powershell Prompt**.
```powershell
conda update --name base --channel defaults conda --yes
conda create --name iblrig python=3.8 --yes
conda activate iblrig
conda install git --yes
git clone https://github.com/int-brain-lab/iblrig C:\iblrig
cd C:\iblrig
git checkout tags/7.0.3
pip install --editable .
pip install pybpod-gui-api==1.8.3b1 pybpod-gui-plugin-alyx==1.1.3b1
pip uninstall ibllib --yes
python setup_pybpod.py
cd Bonsai
setup.bat
cd ..
conda create --name ibllib python=3.8 --yes
conda activate ibllib
pip install ibllib
```

NOTE: ONE will need to be configured for your use case. Please review the ONE [documentation](https://int-brain-lab.github.io/ONE/) for specifics on how to accomplish this. Then run the following command or something similar for your specific setup: `python -c "from one.api import ONE; ONE()"`

### Running pybpod
To run pybpod and begin data acquisition:
```powershell
conda activate iblrig
cd C:\iblrig
.\pybpod.bat
```

#### For easier launching of pybpod
Within the `C:\iblrig` folder there is a `pybpod-Anaconda_Powershell_Prompt.lnk` file that can be copied to the desktop for ease 
of use.
```powershell
Copy-Item "C:\iblrig\pybpod-Anaconda_Powershell_Prompt.lnk" -Destination "$Env:HOMEPATH\Desktop"
```

#### Setup instructions for launching the 'Experiment Description GUI' prior to task launch (DEVELOP)
The 'Experiment Description GUI' is currently being developed in the iblscripts repo. This GUI is intended to simplify the 
categorization of an experiment and cleanly define what projects and procedures an experiment is for. In order to add the GUI to 
the tasks listed in the `add_ex_desc_gui_to_tasks` script, run the following commands from the **Anaconda Powershell Prompt**:
```powershell
conda activate iblrig
git clone -b develop https://github.com/int-brain-lab/iblscripts C:\iblscripts
pip install -r C:\iblscripts\deploy\project_procedure_gui\pp_requirements.txt
```

Within whichever custom task you would like to test this gui, simply add the following lines to `_iblrig_tasks_customTask.py`
* i.e. `C:\iblrig_params\IBL\tasks\_iblrig_tasks_customTask\_iblrig_tasks_customTask.py`

```python
from iblrig.misc import call_exp_desc_gui
call_exp_desc_gui()
```

---
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

---

### Troubleshooting Notes

#### Windows
Disable Microsoft Store associations with `python` command
* Open the Settings or Start menu and search for “App execution aliases” or “Manage app execution aliases” 
* Disable any python entries listed

#### Anaconda
##### Broken Uninstall
* After uninstalling, navigate the file browser to the user home directory (C:\Users\username) and remove all `Anaconda`, 
`.anaconda`, `.conda`, `.condarc`, etc files and folders
  * search the hidden AppData folders as well (different versions of Anaconda stored data in different locations)
* If running the command prompt is no longer functional, run the following command in Powershell:
> Reg Delete "HKCU\Software\Microsoft\Command Processor" /v AutoRun /f
* If Powershell is throwing a warning about an `Activate.ps1` file, remove the profile file from `%userhome%\Documents\Powershell`

##### llvmlite error on ibllib install
While performing a `pip install ibllib` command in a fresh conda environment, an occasional error may occur; `Error: Cannot 
uninstall llvmlite...`. A simple workaround: 
* close all Anaconda Prompts
* open an **Anaconda Powershell Prompt**
* reactivate the ibllib conda environment, `conda activate ibllib`
* run `pip install ibllib`

### Stim display on wrong screen
If the visual stimulus appears on the wrong screen:
* short term, pressing `F11` on the keyboard will unmaximize the window; allowing movement of the stimulus to the correct screen 
* longer term, take note of a file called `C:\iblrig_params\.iblrig_params.json`; within that file is a variable called 
`DISPLAY_IDX`, its value will be set to 0 or 1. If the stimulus screen initially launches on the wrong monitor (PC screen instead 
of iPad screen), then change the value of `DISPLAY_IDX`. Change it to 0 if it was on 1, change it to 1 if it was on 0.
  * Please note, the display index value is something assigned by OS and could potentially change between reboots