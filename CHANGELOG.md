Changelog
=========

8.24.0
------
* add validation script for Bpod HiFi Module (folder `scripts`)
* fix: `_ephysChoiceWorld` - values from the pre-generated sessions were not actually used 
* fix: `_ephysChoiceWorld` - trial fixtures contained inverted values for `probability_left`
* feature: validate values in `trials_table` using Pydantic
* feature: add API documentation

-------------------------------

8.23.1
------
* feature: post hardware information to alyx
* generate PDF documentation
* increase verbosity of error handling in base task
* remove dead code

8.23.0
------
* hardware validation: check for unexpected events on Bpod's digital input ports
* hardware validation: frame2ttl

-------------------------------

8.22.1
------
* get past sessions bugfix when newer sessions are present only on the remote server

8.22.0
------
* add UI components for selecting remote devices

-------------------------------

8.21.2
------
* fix: remote devices show as task parameters (regression)

8.21.1
------
* hotfix: add DISABLE_BEHAVIOR_INPUT_PORTS key to hardware_settings.yaml

8.21.0
------
* display values of automatically inferred task parameters
* store pause durations to trial info
* add backend for UDP communication between rig computers
* use PDM for managing dependencies
* log session call / commandline parameters to disk
* fix: potential deadlock with SerialSingleton
* fix: "galloping" valve during valve calibration
* fix: values computed by "Get Training Phase" in "Tools" menu
* fix: incorrect parsing of adaptive gain value in trainingChoiceWorld

-------------------------------

8.20.0
------
* tab for displaying local sessions and their respective status
* additional task parameters for passiveChoiceWorld
* work on making the GUI code more modular

-------------------------------

8.19.6
------
* hotfix: fix race-condition that caused scrambled online-plots

8.19.5
------
* hotfix: move serial validation from SerialSingleton to Serial

8.19.4
------
* hotfix: fix validation for Alyx when no Alyx URL has been set
* hotfix: fix validation for Bpod HiFi module
* adapted update instructions in update notification & documentation

8.19.3
------
* hotfix: force stimulus to freeze in center of screen during "freeze_reward" state
* method for copying snapshots to the local server using the SessionCopier
* documentation for transition to Bpod HiFi

8.19.2
------
* hotfix: only register water administrations once per protocol
* hotfix: reverse wheel contingency now controlled through task parameter STIM_REVERSE

8.19.1
------
* hotfix: threading warnings during valve calibration (when used without scale)
* hotfix: unreliable exit condition for state machine during valve calibration

8.19.0
------
* automated validation of rig components
* adaptive reward parameter for trainingPhaseChoiceWorld
* add validate_video entry-point
* switch from flake8 to ruff for linting & code-checks
* automatically set correct trigger-mode when setting up the cameras
* support rotary encoder on arbitrary module port
* add ambient sensor reading back to trial log
* allow negative stimulus gain (reverse wheel contingency)

-------------------------------

8.18.0
------
* valve calibration routine

-------------------------------

8.17.0
------
* consolidated data transfer routine across all rig computers
* new video workflow with support for multiple named camera setups
* various small fixes, work on documentation, unit-tests

-------------------------------

8.16.1
------
* Hoferlab: when bpod returns inconsistent error, time-out or correct, throw the exception after logging
* add AMP_TYPE field to hardware_settings.yaml (device_sound) to handle the combination of HiFi module and AMP2x15 amplifier

8.16.0
------
* Support for Bpod HiFi Module
* Support for Zapit Optostim (NM)
* more robust handling of Bpod's serial messages: iblrig.hardware._define_message

-------------------------------

8.15.6
------
* Task specifications: The time from the stimulus offset to the quiescence period is targeted to 1 second instead of 1.5 seconds
* Task specifications: The correct delay time starts running from the start of the reward state, not the end of the reward state.
* Fixed unit-tests

8.15.5
------
* hotfix: show Garbor patch in passive choice-world, GUI option for session ID, no dud detection

8.15.4
------
* hotfix: disable prompt for deleting "duds" for appended sessions 

8.15.3
------
* hotfix: don't wait for microphone workflow to finish

8.15.2
------
* hotfix: pin iblutil to >=1.7.4 to address unicode encoding issue during logging
* hotfix: allow pass with warning in case where lab validation fails due to Alyx down / server issues
* change: use QT workers for Frame2TTL calibration steps
* extra task parameters: support list of strings
* frame2ttl: raise exception on incorrect port setting
* convert_ui: add argument for filename glob

8.15.1
------
* hotfix: correct parsing of description files and ignore junk sessions in iterate_protocols

8.15.0
------
* feature: calibration routine for frame2ttl v1-3 in Tools menu
* feature: debug-flag for IBLRIG Wizard

-------------------------------

8.14.2
------
* hotfix: wrong return-type in _iterate_protocols - pt 2

8.14.1
------
* hotfix: wrong return-type in _iterate_protocols

8.14.0
------
* show dialog boxes and plots for appended sessions

-------------------------------

8.13.5
------
* make sure unused arguments passed up to BaseChoiceWorld do not crash the task (example delay_secs in passiveChoiceWorld)

8.13.4
------
* pin iblutil to version 1.7.3 or later
* reworked upgrade script and moved to separate file to avoid file-access issues
* fixed display of version string in "about" tab
* revert logging of task events to GUI only

8.13.3
------
* add tests with mock Bonsai to cover for task start methods
* hotfix: also log to PowerShell (for now)

8.13.2
------
* hotfix: 'WindowsPath' object has no attribute 'split'

8.13.1
------
* hotfix: passing non-existent parameter to Bonsai workflow

8.13.0
------
* restructured user interface
* script for starting video-session in ephys-rig
* installer scripts for Spinnaker SDK / PySpin
* validated parsing of settings files
* added legend to trials-timeline
* added button for triggering a free reward (only available outside of running task for now)
* cleaned-up logging
* various improvements under the hood, clean-up and unit-tests

-------------------------------

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
* allow pausing between trials
* task-specific settings
* new dialogs for weight & droppings
