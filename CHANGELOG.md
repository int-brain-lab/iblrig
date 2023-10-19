Changelog
---------

-------------------------------

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
