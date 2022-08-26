@echo off
set iblrig_dir=C:\iblrig
set projects_dir=C:\iblrig_params

echo Finding pybpod folder...
chdir /D %projects_dir%

echo Launching pybpod...
call start-pybpod

chdir /D %iblrig_dir%
echo done