@echo off
set iblrig_dir=C:\iblrig
set projects_dir=C:\iblrig_params

echo Activating IBL environment...
call activate iblenv %*

echo Finding iblrig folder...
chdir /D %iblrig_dir%

echo Updating update routines...
call python update.py --update

echo Checking for updates...
call python update.py

echo Finding pybpod folder...
chdir /D %projects_dir%

echo Launching pybpod...
call start-pybpod
echo done