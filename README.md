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

#### Setup instructions for launching the 'Experiment Description GUI' prior to task launch

The 'Experiment Description GUI' is currently being housed on the iblscripts repo. This GUI is intended to simplify the 
categorization of an experiment and cleanly define what projects and procedures an experiment is for. In order to add the GUI to 
a custom task:

* clone the iblscripts repo: `git clone https://github.com/int-brain-lab/iblscripts`
* launch pybpod
* select the custom task protocol to modify
* click on the plus button to add a "pre command"
* use the drop-down box to select `Execute an external command`
* depending on where the iblscripts repo was clones, enter into the text box something like the following:
  * `python C:\iblscripts\deploy\project_procedure_gui\experiment_form.py`

---
## How to develop on this repository 
This repository is adhering to the following conventions:
* [semantic versioning](https://semver.org/) for consistent version numbering logic
* [gitflow](https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow) for managing branches 
* [Flake8](https://flake8.pycqa.org/) for style guide enforcement 

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
