Changelog
---------


8.12.14
-------
* unit-tests and linting

8.12.13
-------
* fix problem with corrupt acquisition descriptions in history

8.12.12
-------
* skipped

8.12.11
-------
* hotfix for creation of bonsai layout-file
* separated installers for Spinnaker SDK and PySpin

8.12.10
-------
* ignore user-side changes to bonsai layouts (for camera workflows only)
* error message if rig-name is not defined in Alyx
* populate delegate users
* the usual: minor fixes, clean-ups and unit-tests

8.12.9
------
* usability improvements for "Show Training Level" tool
* ignore unused behavior ports
* remove unnecessary dependencies

8.12.8
------
* fix incorrect limits & unit for adaptive gain in trainingChoiceWorld  
* usability improvements for "Show Training Level" tool

8.12.7
------
* online plot: fix line colors and add legends
* do not show Bonsai editor during session

8.12.6
------
* reverting TTL on trial end introduced with PR #504, release 8.9.0
* general code maintenance (unit-tests, doc-strings, type-hints, removal of dead code) 

8.12.5
------
* add a tools menu in the wizard to get training level from v7 sessions to ease transition

8.12.4
------
* updated online-plots

8.12.3
------
* bugfix: getting training status of subject not present on local server
* skipping of bpod initialization now optional (used in GUI)
* disable button for status LED if not supported by hardware
* tests, type-hints, removal of dead code

8.12.2
------
* bugfix: rollback skipping of bpod initialization (possible source of integer overflow)
* removal of dead code

8.12.1
------
* bugfix: remember ability for setting the status LED

8.12.0
------
* add a trainingPhaseChoiceWorld task to fix the training levels
* bugfix: copy script prompt accepts both upper case and lower case Y to proceed
* bugfix: update-check used incorrect calls for subprocesses

-------------------------------

8.11.5
------
* bugfix: negative time being displayed in the live-plots

8.11.4
------
* bugfix: incorrect subprocess-calls in version_management

8.11.3
------
* bugfix: 0 contrasts argument overwritten for trainingCW

8.11.2
------
* make custom_tasks optional
* repair lost entry-point for iblrig wizard
* fetch remote tags only if connected to internet

8.11.1
------
* add GUI options for AdvancedChoiceWorld

8.11.0
------
* add check for availability of internet
* add proper CLI for data transfer scripts
* add control for disabling Bpod status LED
* skip initialization of existing Bpod singleton
* remember settings for status LED and GUI position
* move update-check to separate thread 
* detect duds (less than 42 trials) and offer deletion
* various small bugfixes

-------------------------------

8.10.2
------
* hot-fix parsing of path args in transfer_data
* add install_spinnaker command for ... installing spinnaker
* fixed CI warnings about ports that haven't been closed
* draw subject weight for adaptive reward from previous session
* format reward with 1 decimal on online plot

8.10.1
------
* more reliable way to check for dirty repository
* add visual hint for unfilled list-views

8.10.0
------
* adaptive reward from previous sessions in TrainingChoiceWorld
* updater: fetch remote changelog to advertise new features

-------------------------------

8.9.4
-----
* correction for version regex
* fix version strings for compatibility with packaging.version

8.9.3
-----
* re-implemented update notice
* corrected implementation of end session criteria
* set adaptive reward to false temporarily

8.9.2
-----
* hot-fix for disabling the update-check - this will need work

8.9.1
-----
* hot-fix for missing live-plots

8.9.0
-----
* major rework of the GUI
* task-specific settings
* new dialogs for weight & droppings
