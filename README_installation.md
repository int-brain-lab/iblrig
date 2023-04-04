# iblrigv8
Software used to interact with various pieces of specialized hardware for neuroscience data acquisition.

## Installation on Windows
Software has only been tested on Windows 10. No other version of Windows is supported at this time. The test user account has 
administrative rights.

### Prerequisite Software:
In order to install iblrig on a Windows machine please ensure that the following prerequisite is installed first.
- A fully featured text editor is recommended, something like [Notepad++](https://notepad-plus-plus.org/)
- [Git](https://git-scm.com); it is recommended to set notepad++ as your default editor for git
- [Visual C++ Redistributable for Visual Studio 2015](https://www.microsoft.com/en-us/download/details.aspx?id=48145), this is a 
requirement for the matplotlib python package

### Installation Instructions:
- Ensure a stable internet connection is present as several commands will require software to be downloaded

Run the following commands from a **Windows Powershell** prompt

Instal Python 3.8
```powershell
New-Item -ItemType Directory -Force -Path C:\Temp
Invoke-WebRequest -Uri https://www.python.org/ftp/python/3.8.10/python-3.8.10-amd64.exe -OutFile C:\Temp\python-3.8.10-amd64.exe
Start-Process -NoNewWindow -Wait -FilePath C:\Temp\python-3.8.10-amd64.exe -ArgumentList "/passive", "InstallAllUsers=0", "Include_launcher=0", "Include_test=0"
```

Clone and install iblrig.
```powershell
Set-ExecutionPolicy -Scope CurrentUser Unrestricted -Force
cd \
git clone https://github.com/int-brain-lab/iblrig.git iblrigv8
cd iblrigv8
git checkout iblrigv8
C:\Users\IBLuser\AppData\Local\Programs\Python\Python38\.\python.exe -m venv C:\iblrigv8\venv
C:\iblrigv8\venv\scripts\python.exe -m pip install --upgrade pip wheel
```

Install Bonsai from the cloned repository.
```powershell
cd Bonsai
powershell.exe .\install.ps1
```

## Configuration
- settings are relative to the local machine and located in the [settings](settings) directory. 
- task parameters are independent of the hardware settings and located in the task folders. For example, for biasedCW this is 
  found in this [task_parameters.yaml](iblrig_tasks/_iblrig_tasks_biasedChoiceWorld/task_parameters.yaml)
