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


Preparing Windows PowerShell
----------------------------

Open Windows PowerShell in administrator mode:

* Click on the Windows Start button or press the Windows key on your keyboard.
* Type "PowerShell" into the search bar.
* You should see "Windows PowerShell" or "PowerShell" in the search results.
* Right-click on it.
* In the context menu that appears, select "Run as administrator."

Now, run the following command at the prompt of Windows PowerShell:

.. code-block:: powershell

   Set-ExecutionPolicy RemoteSigned -Force

.. tip::

   Keep the Administrator PowerShell open for the next step.

.. admonition:: Background
   :class: seealso

   In PowerShell, there are execution policies that determine the level of security for running scripts. The default execution
   policy is often set to ``Restricted``, which means that scripts are not allowed to run. However, to install Python or run
   certain scripts, you need to adjust the execution policy. By setting the execution policy to ``RemoteSigned``, you are
   allowing the execution of locally created scripts without any digital signature while requiring that remotely downloaded
   scripts (from the internet) must be digitally signed by a trusted source to run. This strikes a balance between security
   and usability.


Installing MS Visual C++ Redistributable
----------------------------------------

With the Administrator PowerShell still open, run the following commands:

.. code-block:: powershell

   New-Item -ItemType Directory -Force -Path C:\Temp
   Invoke-WebRequest -Uri https://aka.ms/vs/17/release/vc_redist.x64.exe  -OutFile C:\Temp\vc_redist.x64.exe
   Start-Process -NoNewWindow -Wait -FilePath C:\Temp\vc_redist.x64.exe -ArgumentList "/install", "/quiet", "/norestart"

.. warning:: Make sure you exit the Administrator PowerShell before continuing with the next steps!

.. admonition:: Background
   :class: seealso

   These commands will create a temporary directory, download and silently install the Visual C++ Redistributable package for
   64-bit Windows systems. The installer is retrieved from a Microsoft server and executed with parameters to ensure a seamless
   and unobtrusive installation process.


Installing Python 3.10
----------------------

Open a `new` Windows Powershell prompt (no administrator mode) and run the following:

.. code-block:: powershell

   New-Item -ItemType Directory -Force -Path C:\Temp
   Invoke-WebRequest -Uri https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe -OutFile C:\Temp\python-3.10.11-amd64.exe
   Start-Process -NoNewWindow -Wait -FilePath C:\Temp\python-3.10.11-amd64.exe -ArgumentList "/passive", "InstallAllUsers=0", "Include_launcher=0", "Include_test=0"

Check that everything worked by running the following command:

.. code-block:: powershell

   &C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python310\python.exe --version

The command should return ``Python 3.10.11``


.. admonition:: Background
   :class: seealso

   These commands will create a temporary directory, download the Python installer from a specific URL, and then execute the
   installer with specific installation options, all in a controlled and automated manner.


Installing iblrigv8
-------------------

1. From the Powershell command line, clone the `iblrigv8` branch of iblrig to ``C:\iblrigv8``:

   .. code-block:: powershell

      git clone -b iblrigv8 https://github.com/int-brain-lab/iblrig.git C:\iblrigv8


2. Install a new virtual environment and update pip:

   .. code-block:: powershell

      &C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python310\python.exe -m venv C:\iblrigv8\venv
      C:\iblrigv8\venv\scripts\python.exe -m pip install --upgrade pip wheel


3. Install iblrig in editable mode:

   .. code-block:: powershell

      C:\iblrigv8\venv\scripts\Activate.ps1
      cd C:\iblrigv8
      pip install -e .


4. Install Bonsai in portable mode:

   .. code-block:: powershell

      cd C:\iblrigv8\Bonsai
      powershell.exe .\install.ps1
      cd ..


5. Install additional tasks and extractors for personal projects (optional):

   .. code-block:: powershell

      git clone https://github.com/int-brain-lab/project_extraction.git C:\project_extraction
      cd C:\project_extraction
      pip install -e .


6. Continue with :ref:`the next section<Configuration instructions>`.


Configuration Instructions
--------------------------

Rig Configuration Files
~~~~~~~~~~~~~~~~~~~~~~~

Copy the template settings files:

.. code-block::

   cd C:\iblrigv8\settings
   cp hardware_settings_template.yaml hardware_settings.yaml
   cp iblrig_settings_template.yaml iblrig_settings.yaml
   explorer C:\iblrigv8\settings


Update the two settings files using a text-editor:

*  ``iblrig_settings.yaml``
*  ``hardware_settings.yaml``

If the computer has been used with IBLRIG version 7 or earlier, the correct values can likely be found in ``C:\iblrig_params\
.iblrig_params.json``.


Setting up ONE
~~~~~~~~~~~~~~


Setup ONE to connect to https://alyx.internationalbrainlab.org, you will need your Alyx username and password.

See instructions for that here: https://int-brain-lab.github.io/iblenv/notebooks_external/one_quickstart.html


.. exercise:: Make sure you can connect to Alyx !

   Open a Python shell in the environment and connect to Alyx (you may have to setup ONE)

   .. code-block::

      C:\iblrigv8\venv\scripts\Activate.ps1
      ipython

   Then at the IPython prompt

   .. code-block:: python

      from one.api import ONE
      one = ONE(username='your_username', password='your_password', base_url='https://alyx.internationalbrainlab.org')


.. exercise:: You can check that everything went fine by running the test suite:

   .. code-block:: powershell

      cd C:\iblrigv8
      python -m unittest discover

   The tests should pass to completion after around 40 seconds


Updating iblrigv8
-----------------

To update iblrigv8 to the newest version:

   .. code-block:: powershell

      C:\iblrigv8\venv\scripts\Activate.ps1
      upgrade_iblrig


If you're on an older version of iblrigv8, the command above may not be available yet.
You can then run the following instead:

   .. code-block:: powershell

      C:\iblrigv8\venv\scripts\Activate.ps1
      cd C:\iblrigv8
      git pull
      pip install --upgrade -e .


To update the additional tasks and extractors (see :ref:`Installing iblrigv8`, point 5):

   .. code-block:: powershell

      cd C:\project_extraction
      git pull
