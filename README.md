# IBL_root

IBL_root is the root folder for the PyBpod/Bonsai task. It requires, for now, to be installed in the root C:\ folder of your windows computer.

IBL_root is using gitflow and semantic versioning conventions.
More on gitflow: https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow
More on semantic versioning: https://semver.org/

If a branch exists, with version number hyphen "patch" e.g. 1.0.0-patch ,
this means that version 1.0.0 is supported for the time being.
While no new functionality will be added, it will recieve bug fixes and
the patch version number might change.

## Dependencies
Git, Anaconda and Bonsai. Before starting you should have git installed.


## Installation
0. Bonsai needs to be installed in your system as the task will call a Bonsai workflow to display the visual stimulus.
You can download Bonsai from here (http://bonsai-rx.org/). After installing it you should also install some relevant Bonsai packages from the overhead menu in Tools --> Manage Packages. A list of relevant packages is upcoming, but for now you can install all of them, sorry if the process is slightly tedious.
**Note:** If using PointGrey cameras the FlyCap Viewer 32bits AND 64bits should be installed otherwise the PointGrey reletad node won't show.

1. Install the Anaconda python distribution to your system, you can get it from here:
https://www.anaconda.com/download/#windows
Anaconda for windows will ask you to install vs code. VS code is a cross platform editor for various programming languages. It's OK to install it if you want. On first run, VS code will ask you to install some packages including git. If you chose to install VS code just go ahead and install all requires packages including Git.

2. Install Git. If you installes VS code in the previous step you can skip this part. If you decided not to install VS code you will have to download and install Git from here: https://github.com/git-for-windows/git/releases/ (pick the latest 64bit vesrion).

3. Checkout this repository in your **root folder C:\\>**
```posh
C:\>git clone --recursive https://github.com/int-brain-lab/IBL_root.git
```
This might take a while.

Your IBL_root folder should now look like this:
*Bonsai_workflows
pybpod
pybpod_data
pybpod_projects
water-calibration-plugin*

4. Open an Anaconda prompt, navigate to C:\\IBL_root and type:
```posh
(base) C:\IBL_root>python install.py
```
This will also take a while and should get your system up and running.
You'll be prompted multiple times by the script, the answer is always yes.

## Running pybpod
There is a \*.bat file that will make sure you load the python environment and run the PyBpod GUI in the IBL_root.
From an Anaconda prompt just type:
```posh
(base) C:\IBL_root>pybpod
```
Alternatively if you add IBL_root to the system path you can type pybpod from any folder of the Anaconda prompt.

## Updating the task and software
Updating should be as simple as typing:
```posh
(base) C:\IBL_root>python update.py
```
For more information on how to update you can use the flags [ -h | --help | ? ] e.g:
```posh
(base) C:\IBL_root>python update.py -h

Usage:
    update.py
        Will fetch changes from origin. Nothing is updated yet!
        Calling update.py will display information on the available versions
    update.py <version>
        Will checkout the <version> release and update the submodules
    update.py -h | --help | ?
        Displays this docstring.

```
