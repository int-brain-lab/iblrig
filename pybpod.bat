@echo off
::echo Adding current directory to system path...
::set path="%path%;C:\iblrig\"
::PAUSE
echo Finding pybpod folder...
set projects_dir=C:\iblrig\pybpod_projects
chdir /D %projects_dir%

echo Activating IBL environment...
call activate iblenv %*

echo Launching pybpod...
::call python -m pybpodgui_plugin %*
call start-pybpod
echo done
