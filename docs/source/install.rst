Installation
============

iblrig
------

iblrig is the main folder for the PyBpod/Bonsai task. It requires, for now,
to be installed in the root **C:\\folder** of your windows computer.

iblrig is using gitflow and semantic versioning conventions.

| More on gitflow: https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow
| More on semantic versioning: https://semver.org/

If a branch exists, with version number hyphen "patch" e.g. 1.0.0-patch ,
this means that version 1.0.0 is supported for the time being.
While no new functionality will be added, it will recieve bug fixes and
the patch version number might change.

Dependencies
------------

Anaconda python distribution, Bonsai and Git.
Before starting you should have Anaconda and git installed.


Anaconda Python distribution
____________________________

Install the Anaconda python distribution to your system,
you can get it from here: https://www.anaconda.com/download/#windows

Anaconda for windows will ask you to install vs code.
VS code is a cross platform editor for various programming languages.
It's OK to install it if you want.
On first run, VS code will ask you to install some packages including git.
If you chose to install VS code just go ahead and install all requires packages
including Git (you can skip installing it manually later on).

Git
___

Install Git.
If you installed VS code in the previous step and installed git after VS code
prompted you, you can skip this part.
If you decided not to install VS code you will have to download and install Git
from here: https://github.com/git-for-windows/git/releases/
(pick the latest 64bit vesrion).

Installing the repository
-------------------------

Checkout this repository in your **root folder C:\\>**

::

  C:\>git clone --recursive https://github.com/int-brain-lab/iblrig.git

Your iblrig folder should now have the following folders:

::

 Bonsai
 docs
 pybpod
 pybpod_projects
 Subjects
 visual_stim

and the following files:

::

 .gitignore
 .gitmodules
 install.py
 pybpod.bat
 README.md
 update.py
 user_settings.py

Open an Anaconda prompt, navigate to **C:\\iblrig>** and type:

::

 (base) C:\iblrig>python install.py

**NOTE:** Use the Anaconda prompt and not the windows prompt or PowerShell.
This will also take a while and should get your system up and running.
You'll be prompted multiple times by the script, please read the instructions.


Bonsai
______

The correct Bonsai vesrion that runs the visual stimulus has been packaged with
the rig code and 'lives' in a folder called iblrig\Bonsai the installation
process is going to ask you to configure Bonsai at some point.
The Bonsai bootstrapper will install all the required dependencies and drop you
in the package manager.

Please **install all packages** except the Bonsai.Numeric (on the last page).
You can change any of these configurations any time by accessing the overhead
menu in Tools --> Manage Packages.
A list of relevant packages is upcoming, until then, a tip:
in page 2 of the package manager there is a package called
**Bonsai.StarterPack**, start by installing this one it will install a bunch of
packages for you and save you some clicks.

Please also **update all updatable packages** by selecting updates in the left
hand menu and finally **install the Bonsai.Bpod** package which you can find by
selecting "Include pre-releases" at the top of the package manager,
sorry if the process is slightly tedious.

**Note:** If using PointGrey cameras the FlyCap Viewer 32bits AND 64bits should
be installed otherwise the PointGrey reletad node won't show.

Info on Bonsai (http://bonsai-rx.org/).


PyBpod
______

After having installed Bonsai the install script will ask you to run some commands.

::

 (base) C:\iblrig>activate pybpod-environment && cd pybpod
 (pybpod-environment) C:\iblrig\pybpod>python utils\install.py

If no red text pops up you should be ready to go.


Running pybpod
--------------

There is a \*.bat file that will make sure you load the python environment
and run the PyBpod GUI.

From an Anaconda prompt, again, navigate to **C:\\iblrig>** and type:

::

 (base) C:\iblrig>pybpod

Alternatively, if you add the iblrig folder to the system path you can type
**pybpod** from any folder avoiding to have to **cd C:\\iblrig** before running
PyBpod.


Running a protocol
------------------

The PyBpod UI is still a work in progress and some things are not obvious.
All the information on PyBpod and its modules can be found  here
(https://pybpod.readthedocs.io/en/master/).

In order to run a task you will need to configure the task code for your
particular system. At the moment the task that is distribuited is called
basicChoiceWorld and you should have a basicChoiceWorld and a
test_basicChoiceWorld experiments already setup.
The protocol however, needs to know both the COM port of Bpod and the COM port
of your rotary encoder module.
To figure out which is which you can use windows device manager -> COM Ports and
plug the device in and out to see which number re-appears.
To set the COM port of Bpod, under boards (on the left side panel) select box0.
This brings up a panel on the righthand side, type in the correct COM port for
your Bpod and test it by clicking the load button underneath.
Bpod's LED should flash green for a moment and you should see a bunch of
information appear in the panel.
Go to the last tab (active ports) and select BNC1, BNC2 and Port1, deselect the
rest as these ports will not be used by the task.

Finally, the rotary encoder, as well as all other task related settings, can be
found and configured in a file called **task_settings.py** inside the task code
folder. You should review these settings and set them to the desired values.

PyBpod does not allow you to run a task without a user and a subject.
To "login" as a user you just need to double-click on your user under "users".
If your user is not there you can create one by right clicking and editing the
name on the righthand side text box that should have appeared.

To actually run an experiment you need to setup a ... a "setup".
Under Experiments you can find a couple of them already configured.
Basically a "setup" is a specific combination of a Bpod board, a task protocol,
and an experimental subject, all ran by a user.
Once this experiment (or setup) is configured you can select it and run the
task. (The IBL task should be ran in detached mode, checkbox to the left of the
"run" button).

To stop a task press "stop" and if the task doesn't stop, press "stop trial".
(More on PyBpod and task usability coming soon...)


Updating the task and software
------------------------------

The update function will save your rig's configuration so you shouldn't have to
reconfigure COM ports, subjects, users, tasks, and experiments.
Updating should be as simple as typing:

::

 (base) C:\iblrig>python update.py


For more information on how to update you can use the flags
[ -h | --help | ? ] e.g:

::

 (base) C:\iblrig>python update.py -h

 Usage:
    update.py
        Will fetch changes from origin. Nothing is updated yet!
        Calling update.py will display information on the available versions
    update.py <version>
        Will backup pybpod_projects folder where local configurations live.
        Will checkout the <version> release, update the submodules, and restore
        the pybpod_projects folder from backup.
    update.py tasks
        Will checkout any task file not present in the local tasks folder.
    update.py tasks <branch>
        Will checkout any task file from <branch> not present in local folder.
    update.py -h | --help | ?
        Displays this docstring.
