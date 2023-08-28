**************************
Frequently Asked Questions
**************************

Here we collect common issues and questions regarding IBLRIG.


First Aid
=========

Here are the first steps to follow if your IBLRIG isn't functioning properly:

*  Employ the automated test-script bundled with IBLRIG. This script helps identify common issues.
   Execute it using PowerShell:

   .. code:: powershell

      C:\iblrigv8\venv\scripts\Activate.ps1
      python C:\iblrigv8\scripts\hardware_validation\verify_hardware.py

*  Check `the comprehensive user manual <https://doi.org/10.6084/m9.figshare.11634732.v6>`__.
   Verify if all connections are secure, and configurations align with the manual's guidelines.

*  Should challenges persist, don't hesitate to contact our developer team for assistance. We're committed to getting your system back on track.


Bug Alert!
==========

Indeed, bugs are persistently present. Our team is in a perpetual quest to eliminate these pesky issues. Your
contribution is invaluable in this endeavor; kindly consider `creating an issue on GitHub <https://github.com/int-brain-lab/iblrig/issues>`_.

Feature Request?
================

IBLRIG remains in dynamic development, tailored to meet your needs. Your input shapes our direction. `Send us your
feature-requests via GitHub <https://github.com/int-brain-lab/iblrig/issues>`_ - we will do our best to help you.


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

* The ribbon cable attaching the screen to the driver board is notoriously finicky. If you are having brightness issues or do not have a signal, try gently repositioning this cable and ensure it is tightly seated in its connection.
* These screens (especially with this cable) can be easily damaged. It is useful to have a backup screen on hand.
* If the Bonsai display is appearing on the PC screen when a task starts, try unplugginstimulg the rig screen, rebooting and plugging screen back in. Other variations of screen unplugging and rebooting may also work.
* Screen flashing can occur if the power supply does not match the screen specifications. Use a 12V adapter with at least 1A.
