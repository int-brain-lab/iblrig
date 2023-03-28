## Configuration of iblrig tasks
This folder contains the necessary settings to instantiate a task. The intent is to ultimately keep only hardware settings. but the current configuration files include:
-  **hardware settings**: is the rig hardware configuration. It is a hierarchical file that contains potentially rig specifc information, such as COM ports and hardware calibration information.
-  **iblrig settings**: are configuration related to the iblrig repository and the folder structure of task related data
 
## Installation instructions
Only templates are provided. On installation files should be copied by removing `_template` part of the file name such as 
- `iblrig_settings_template.py` -> `iblrig_settings.py`
- `hardware_settings_template.py` -> `hardware_settings.py`

Those files are git ignored and will not be committed to the repository.
