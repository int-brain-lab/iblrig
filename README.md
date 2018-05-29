# IBL_root

IBL_root is the root folder for the PyBpod/Bonsai task. It requires, for now, to be installed in the root C:\ folder of your windows computer.

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

4. Now we need to create a python environment to run PyBpod and the task. Luckily PyBpod comes with an environment file ready for that. It will create a python environment called pybpod-environment which has almost all the libraries we need.  
```posh
(base) C:\>cd IBL_root\pybpod
(base) C:\IBL_root\pybpod>conda env create -f environment-windows-10.yml  
(base) C:\IBL_root\pybpod>conda activate pybpod-environment`
```
5. We might need to update conda, to do so just run:  
```posh
(pybpod-environment) C:\IBL_root\pybpod>conda update -n base conda
```
6. We now need to install some more dependencies for the task plotting and communications with the sound card and Bonsai. For the plotting we'll use the conda package manager:  
```posh
(pybpod-environment) C:\IBL_root\pybpod>conda install scipy
(pybpod-environment) C:\IBL_root\pybpod>conda install pandas
```
### WARNING: DO NOT UPGRADE PIP!!  
You might come actross this message:  
```console
You are using pip version 9.0.3, however version 10.0.1 is available.
You should consider upgrading via the 'pip install --upgrade pip' command.  
```
However updating pip this way will break it. Basically, pypi.org stopped accepting TLS<1.2 connections and updating pip this way will break it.  Ignore the message and proceede.  
For the communication with soundcard and Bonsai run:
```posh
(pybpod-environment) C:\IBL_root\pybpod>pip install sounddevice
(pybpod-environment) C:\IBL_root\pybpod>pip install python-osc
```
7. Now you can install PyBpod by opening an anaconda prompt navigating to the pybpod folder and simply typing:    
```posh
(pybpod-environment) C:\IBL_root\pybpod>python install.py
```  
The detailed instructions of pybpod installation can be found here https://bitbucket.org/fchampalimaud/pybpod

8. Almost done. In your IBL_root folder you'll find a filed named `user_settings.py` this is a configuration file for pybpod that needs to be copied in the to pybpod folder. 

9. Finally, to install the water calibration plugin just run:
```posh
(pybpod-environment) C:\IBL_root\pybpod>cd ..\water-calibration-plugin
(pybpod-environment) C:\IBL_root\water-calibration-plugin>pip install
('python setup.py install' should also work)
```
## Running pybpod
There is a \*.bat file that will make sure you load the python environment and run the PyBpod GUI in the IBL_root.  
From an Anaconda prompt just type:
```posh
(base) C:\IBL_root>pybpod
```
Alternatively if you add IBL_root to the system path you can type pybpod from any folder.

## Updating the task and software
Updating should be as simple as doing a git pull. Hopefully in the next weeks we'll get to some stability, for now things are changing a lot and I'm sure bugs will appear that need fixing ASAP. My plan is to only use a Master branch with tags, but this might change.
