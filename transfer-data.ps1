# Set the execution policy for powershell
Set-ExecutionPolicy -Scope CurrentUser Bypass -Force

# Activates the python venv environment
C:\iblrig\venv\Scripts\.\Activate.ps1

# Transfer the rig data from the local rig to the server
python C:\iblrig\scripts\transfer_rig_data.py C:\iblrig_data\Subjects Y:\Subjects
