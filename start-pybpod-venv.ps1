Set-ExecutionPolicy -Scope CurrentUser Bypass -Force

# Activates the python venv environment
C:\iblrig\venv\Scripts\.\Activate.ps1

# Must be in the C:\iblrig_params dir to launch pybpod
cd C:\iblrig_params

# start-pybpod command is created when pybpod is installed as a pip package (including when in editable mode)
start-pybpod

# Keep powershell console open after pybpod process completes
Read-Host -Prompt "Press Enter to exit"