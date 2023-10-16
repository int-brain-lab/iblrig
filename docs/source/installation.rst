Installation guide
==================

.. prerequisites::

   *  A computer running Windows 10 or 11,
   *  A working installation of `git for windows <https://gitforwindows.org>`_, and
   *  `Notepad++ <https://notepad-plus-plus.org>`_ or some other decent text editor.

.. tip::

   iblrigv8 can be installed alongside older versions of iblrig without affecting the latter.

.. tip::

   If you believe this guide is incomplete or requires improvements, please don't hesitate to reach out and
   :ref:`submit a bug report<Bug Reports & Feature Requests>`.


Prepare Windows PowerShell
--------------------------

Open Windows PowerShell in administrator mode:

* Click on the Windows Start button or press the Windows key on your keyboard.
* Type "PowerShell" into the search bar.
* You should see "Windows PowerShell" or "PowerShell" in the search results.
* Right-click on it.
* In the context menu that appears, select "Run as administrator."

Now, run the following command at the prompt of Windows PowerShell:

.. code-block:: powershell

   Set-ExecutionPolicy RemoteSigned

.. warning:: Make sure you exit the Administrator PowerShell before continuing with the next steps!

.. admonition:: Background
   :class: seealso

   In PowerShell, there are execution policies that determine the level of security for running scripts. The default execution
   policy is often set to ``Restricted``, which means that scripts are not allowed to run. However, to install Python or run
   certain scripts, you need to adjust the execution policy. By setting the execution policy to ``RemoteSigned``, you are
   allowing the execution of locally created scripts without any digital signature while requiring that remotely downloaded
   scripts (from the internet) must be digitally signed by a trusted source to run. This strikes a balance between security
   and usability.


Install Python 3.10
-------------------

Open a `new` Windows Powershell prompt (no administrator mode) and run the following:

.. code-block:: powershell

   New-Item -ItemType Directory -Force -Path C:\Temp
   Invoke-WebRequest -Uri https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe -OutFile C:\Temp\python-3.10.11-amd64.exe
   Start-Process -NoNewWindow -Wait -FilePath C:\Temp\python-3.10.11-amd64.exe -ArgumentList "/passive", "InstallAllUsers=0", "Include_launcher=0", "Include_test=0"

Check that everything worked by running the following command:

.. code-block:: powershell

   C:\Users\IBLuser\AppData\Local\Programs\Python\Python310\.\python.exe --version

The command should return ``Python 3.10.11``


.. admonition:: Background
   :class: seealso

   These commands will create a temporary directory, download the Python installer from a specific URL, and then execute the
   installer with specific installation options, all in a controlled and automated manner.


Install iblrigv8
----------------

1. From the Powershell command line, clone the `iblrigv8` branch of iblrig to ``C:\iblrigv8``:

   .. code-block:: powershell

      git clone -b iblrigv8 https://github.com/int-brain-lab/iblrig.git C:\iblrigv8


2. Install a new virtual environment and update pip (modify the <Username> value if needed)

   .. code-block:: powershell

      C:\Users\IBLuser\AppData\Local\Programs\Python\Python310\.\python.exe -m venv C:\iblrigv8\venv
      C:\iblrigv8\venv\scripts\python.exe -m pip install --upgrade pip wheel


3. Install iblrig in editable mode

   .. code-block:: powershell

      C:\iblrigv8\venv\scripts\Activate.ps1
      cd C:\iblrigv8
      pip install -e .


4. Install additional tasks and extractors for personal projects (optional)

   .. code-block:: powershell

      cd C:\
      git clone https://github.com/int-brain-lab/project_extraction.git
      cd project_extraction
      pip install -e .


5. Install Bonsai in portable mode

   .. code-block:: powershell

      cd C:\iblrigv8\Bonsai
      powershell.exe .\install.ps1
      cd ..


Update iblrigv8
---------------

   .. code-block:: powershell

      C:\iblrigv8\venv\scripts\Activate.ps1
      cd C:\iblrigv8
      upgrade_iblrig

   alternatively, run:

   .. code-block:: powershell

      C:\iblrigv8\venv\scripts\Activate.ps1
      cd C:\iblrigv8
      git pull
      pip install --upgrade -e .


Configuration instructions
--------------------------


Rig configuration files
~~~~~~~~~~~~~~~~~~~~~~~

Copy template settings files.

.. code-block::

   cd C:\iblrigv8\settings
   cp hardware_settings_template.yaml hardware_settings.yaml
   cp iblrig_settings_template.yaml iblrig_settings.yaml
   explorer C:\iblrigv8\settings


Update the 2 settings files, these values can likely be found in the `C:\iblrig_params\.iblrig_params.json` file if working with a existing rig

*  iblrig_settings.yaml
*  hardware_settings.yaml


Setup ONE
~~~~~~~~~


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
      one = ONE(username='your_username', password='your_password', base_url='https://alyx.internationalbrainlab.org')


.. exercise:: You can check that everything went fine by running the test suite:

   .. code-block:: powershell

      cd C:\iblrigv8
      python -m unittest discover

   The tests should pass to completion after around 40 seconds
