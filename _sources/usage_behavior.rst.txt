Running a behaviour experiment
==============================

IBLRIG v8 provides users with two distinct interfaces: a command line interface (CLI) and a graphical user interface (GUI).
The CLI encompasses the complete functionality of IBLRIG, upon which the GUI is constructed to enhance user-friendliness.
All tasks achievable through the GUI are equally achievable through the CLI.


The Graphical User Interface
----------------------------

To initiate a task through the graphical user interface, open a Windows PowerShell and enter:

.. code:: powershell

   C:\iblrigv8\venv\scripts\Activate.ps1
   iblrig

These commands activate the necessary environment and launch the IBL
Rig Wizard GUI window, as shown below:

.. figure:: gui.png
   :alt: A screenshot of IBL Rig Wizard
   :align: center

   A screenshot of IBL Rig Wizard


Starting a Task
~~~~~~~~~~~~~~~

1. Enter your Alyx username, then click on the *Connect* button. This
   action will automatically populate the GUI fields with information
   pertinent to your lab.

2. Select the desired values from the provided options. Utilize the
   *Filter* field to swiftly narrow down the list of displayed subjects.
   Note that selections for *Project* and *Procedure* are mandatory.

3. Click the *Start* button to initiate the task.


Supplementary Controls
~~~~~~~~~~~~~~~~~~~~~~

-  If you check the *Append* option before clicking *Start*, the task
   you initiate will be linked to the preceding task, creating a
   sequence of connected tasks.

-  The *Flush* button serves to toggle the valve for cleaning purposes.

.. note::
   IBLRIG's Graphical User Interface is still work-in-progress. If you have any suggestions to make the GUI
   more usable, please add an `issue on GitHub <https://github.com/int-brain-lab/iblrig/issues>`_ or approach the dev-team on Slack!
   We are happy to discuss possible changes with you!


The Command Line Interface
--------------------------

To use the command line interface, open a terminal and activate the
environment:

.. code:: powershell

   cd C:\iblrigv8\
   venv\scripts\Activate.ps1

Running a single task
~~~~~~~~~~~~~~~~~~~~~

To run a single task, execute the following command:

.. code:: powershell

   python .\iblrig_tasks\_iblrig_tasks_trainingChoiceWorld\task.py --subject algernon --user john.doe

Chaining several tasks together
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To chain several tasks together, use the ``--append`` flag. For
instance, to run a passive task after an ephys task:

1. Run the ephys task

   .. code:: powershell

      .\iblrig_tasks\_iblrig_tasks_ephysChoiceWorld\task.py --subject algernon

2. Run the passive task with the ``--append``\ flag:

   .. code:: powershell

      .\iblrig_tasks\_iblrig_tasks_passiveChoiceWorld\task.py --subject algernon --append

Flushing the valve
~~~~~~~~~~~~~~~~~~

To flush valve 1 of the Bpod, type ``flush`` and confirm with ENTER. Press ENTER again to close the valve.
