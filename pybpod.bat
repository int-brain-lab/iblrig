@echo off
::echo Adding current directory to system path...
::set path="%path%;C:\iblrig\"
::PAUSE
echo Finding pybpod folder...
set pybpod_dir=C:\iblrig\pybpod
chdir /D %pybpod_dir%

echo Activating pybpod-environment...
call activate pybpod-environment %*

echo Launching pybpod...
call python -m pybpodgui_plugin %*

echo done
