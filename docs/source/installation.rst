Install iblrig
==============

Pre-requisistes:
*   Windows OS
*   git installation.
*   Python 3.10 installation.


Install Python 3.10
-------------------

Open an Administrator: Windows Powershell prompt and run the following:

.. code-block:: powershell

    New-Item -ItemType Directory -Force -Path C:\Temp
    Invoke-WebRequest -Uri https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe -OutFile C:\Temp\python-3.10.11-amd64.exe
    Start-Process -NoNewWindow -Wait -FilePath C:\Temp\python-3.10.11-amd64.exe -ArgumentList "/passive", "InstallAllUsers=0", "Include_launcher=0", "Include_test=0"


.. exercise:: You can check that everything worked by running the following command:

    .. code-block:: powershell

        C:\Users\IBLuser\AppData\Local\Programs\Python\Python310\.\python.exe --version

    Should return `Python 3.10.11`

**Make sure you exit the Administrator Powershell prompt before going to the next steps**


Install iblrigv8
----------------

From the Powershell command line, clone iblrig to the ‘iblrigv8’ directory, and switch to iblrigv8 branch

.. code-block:: powershell

    cd C:\
    git clone https://github.com/int-brain-lab/iblrig.git iblrigv8
    cd iblrigv8
    git checkout iblrigv8

Install a new virtual environment and update pip (modify the <Username> value if needed)

.. code-block:: powershell

    C:\Users\IBLuser\AppData\Local\Programs\Python\Python310\.\python.exe -m venv C:\iblrigv8\venv
    C:\iblrigv8\venv\scripts\python.exe -m pip install --upgrade pip wheel


Install iblrig in editable mode

.. code-block:: powershell

    C:\iblrigv8\venv\scripts\Activate.ps1
    cd C:\iblrigv8
    pip install -e .
    pip install -r requirements.txt

Install Bonsai in portable mode

.. code-block:: powershell

    cd C:\iblrigv8\Bonsai
    powershell.exe .\install.ps1
    cd ..


.. exercise:: You can check that everything went fine by running the test suite:

    .. code-block:: powershell

        cd C:\iblrigv8
        python -m unittest discover

    The tests should pass to completion after around 40 seconds



Configuration instructions
__________________________

Create configuration files from template files

.. code-block::

    cd C:\iblrigv8\settings
    cp hardware_settings_template.yaml hardware_settings.yaml
    cp iblrig_settings_template.yaml iblrig_settings.yaml
    explorer C:\iblrigv8\settings


Update the 2 settings files, these values can likely be found in the ‘C:\iblrig_params\.iblrig_params.json’ file if working with a existing rig

*   iblrig_settings.yaml
*   hardware_settings.yaml


Setup ONE to connect to https://alyx.internationalbrainlab.org, you will need your Alyx username and password.

See instructions for that here: https://int-brain-lab.github.io/iblenv/notebooks_external/one_quickstart.html


.. exercise:: Make sure you can connect to Alyx !
    Open a Python shell in the environment and connect to Alyx (you may have to setup ONE)

    .. code-block::

        C:\iblrigv8\venv\scripts\Activate.ps1
        ipython

    Then at the Ipython prompt

    .. code-block:: python

        from one.api import ONE
        one = ONE()
