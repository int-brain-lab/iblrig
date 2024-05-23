**************************
Frequently Asked Questions
**************************

Here we collect common issues and questions regarding IBLRIG.

First Aid
=========

If your rig is acting up:

*  Employ the **automated test-script** bundled with IBLRIG. This script helps identify common configuration issues.
   Execute it using PowerShell:

   .. code:: powershell

      C:\iblrigv8\venv\scripts\Activate.ps1
      validate_iblrig

*  Check `the comprehensive user manual <https://doi.org/10.6084/m9.figshare.11634732.v6>`__ ("Appendix 3" on GoogleDrive).
   Verify if all connections are secure, and configurations align with the manual's guidelines.

*  Don't hesitate to **contact our developer team** for assistance. We're committed to getting your system back on track.


Bug Reports & Feature Requests
==============================

IBLRIG remains in dynamic development. Your input is invaluable in shaping its direction. `Send us your
bug reports and feature-requests via GitHub <https://github.com/int-brain-lab/iblrig/issues>`_ - we will do our best to help you.


Sound Issues
============

* Double-check all wiring for loose connections.

* Is ``hardware_settings.yaml`` set up correctly? Valid options for sound ``OUTPUT`` are:

  - ``harp``,
  - ``xonar``, or
  - ``sysdefault``.

  Make sure that this value matches the actual soundcard used on your rig.


Screen Issues
=============

General
^^^^^^^

*  The ribbon cable attaching the screen to the driver board is notoriously finicky. If you are having brightness issues or do not have a signal, try gently repositioning this cable and ensure it is tightly seated in its connection.
*  Screen and ribbon cable can be easily damaged. It is useful to have backup at hand.
*  Screen flashing can occur if the power supply does not match the screen specifications. Use a 12V adapter with at least 1A.
*  If the Bonsai display is appearing on the PC screen when a task starts, try unplugging the rig screen, rebooting and plugging the screen back in. Other variations of screen unplugging and rebooting may also work.
   Also make sure, that the ``DISPLAY_IDX`` value in ``hardware_settings.yaml`` is set correctly.

Defining Default Position & Size of Bonsai Visualizers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Is the preview window of the video recording showing on the iPad screen instead of the computer's main display during a
session? To redefine the default position and size of the Bonsai visualizer:

#. Open the Bonsai executable distributed with IBLRIG: ``C:\iblrigv8\Bonsai\Bonsai.exe``.
#. Open the respective Bonsai workflow:

   .. code::

      C:\iblrigv8\devices\camera_recordings\TrainingRig_SaveVideo_TrainingTasks.bonsai

#. Start the workflow by clicking on the play-button.
#. Adjust the position and size of the windows as per your preference.
#. Stop the workflow.
#. Save the workflow.


Frame2TTL
=========

*  Version 1 of Frame2TTL won't be detected after restarting the computer.
   Unplugging and replugging the USB cable should make it responsive again.
*  If IBLRIG complains about not receiving any TTL signals from Frame2TTL:

   *  Ensure Frame2TTL's sensor is positioned over the bottom-right corner of the rig's screen.
      Secure the sensor's cable to the screen mount with a zip-tie to prevent it from slipping off the screen.
      Additionally, use a piece of electrical tape to hold the sensor in place.

   *  Verify that the sensor is connected to Frame2TTL with the correct polarity

      *  Version 1: GND = black cable, SIG = white cable
      *  Version 2 and 3: BLK = black cable, WHT = white cable
   *  Ensure that Frame2TTL's TTL Output is plugged into Bpod's TTL Input #1.
      Note that versions 2 and 3 of Frame2TTL have a second BNC output labeled "analog" - this is *not* the TTL output.
   *  Recalibrate Frame2TTL using the calibration routine in IBLRIG's Tools menu and check for any errors.

*  If the above steps do not resolve the issue, try the following:

   #. Swap out the BNC cable between Frame2TTL and Bpod.
      Use a single cable without any branches.
   #. Connect an oscilloscope to the Bpod end of the cable and run a calibration.
      Look for a voltage step in Frame2TTL's output when the calibration routine switches from dark to light.
   #. If you *do* see the change in the TTL signal, the Bpod might be faulty. Try using a different Bpod unit.
   #. If you do *not* see the voltage step, the Frame2TTL might be faulty. Try using a different Frame2TTL unit.
