# iblrig

iblrig is using gitflow and semantic versioning conventions. Click on the following links for more information on 
[gitflow](https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow) or [semantic versioning](https://semver.org/).

---
## How to work with this repository
### New feature branches:
- `new_feature` branches are forked from the current `develop` branch
- the `new_feature` branches are then merged back into the `develop` branch
- the `new_feature` branch will eventually be deleted

### Release candidate branches:
- a release candidate, `rc` branch is a "pre-release" branch for beta testers on production rigs
- the `rc` branch is forked from the `develop` branch
- once the `rc` has been thoroughly tested, it will be merged into `master` and `develop`
- the `rc` branch will eventually be deleted

### Hotfix branches:
- a `hotfix` or `maintenance` branch is forked from `master`
- once the fix has been thoroughly tested, it will get merged back into `master`, `develop`, `rc`
- the `hotfix` branch will eventually be deleted

---
## Installation of this software suite on Windows
### Prerequisite Software:
In order to install iblrig on a Windows machine please ensure that the following prerequisite is first installed:
- [Anaconda](https://anaconda.com)

### Installation Instructions:
- Ensure Anaconda, git, and your favorite text editor are already installed
  - Please also ensure a stable internet connection is present as the installer pulls from various servers throughout the installation process
- Clone the latest version of this repository to the root of the `C:\` drive
- Open your Anaconda Prompt and navigate `C:\iblrig` 
- At the prompt, run: `python .\install.py`
- The installer will take over for a while and ensure the rest of the requisite software is present
- The installer will prompt you to install ONE (yes/no)
  - If you decide to install ONE, various prompts will assist you in the default configuration
  - _TODO: Add and document better error catching/handling for when these settings are incorrect_
- The installer will prompt you to install Bonsai (yes/no)
- Installation complete

### Installation Notes for manual fresh installation on Python 3.8:
The following commands are to be run from the Anaconda Powershell Prompt. 
```commandline
cd \
conda activate base
conda install git --yes
git clone https://github.com/int-brain-lab/iblrig
cd iblrig
git checkout feature/7.0.0
- TODO: remove once moved to production
conda create --name iblrig python==3.8.13 --yes
conda activate iblrig
pip install --editable .
python setup_pybpod.py
cd Bonsai
install.ps1
cd ..
conda create --name ibllib python==3.8.13 --yes
conda activate ibllib
pip install ibllib
python -c "from one.api import ONE; ONE()"
```
*** NOTE: several prompts will require interaction to configure ONE at this point ***
```commandline
conda activate iblrig
pybpod.bat
```

### Running pybpod
- Navigate your Anaconda Prompt to `C:\iblrig`
- At the prompt, run: `.\pybpod.bat`
- _TODO: More instruction on how to work with the software? Other options?_