## Configuration of iblrig tasks
This folder settings contains the necessary settings to instantiate a task. The intent is to ultimately keep only hardware 
settings. 
but the current configuration files include:
-  **hardware settings**: is the rig hardware configuration. It is a hierarchical file that contains potentially rig specifc 
information, such as COM ports and hardware calibration information.
-  **iblrig settings**: are configuration related to the iblrig repository and the folder structure of task related data
 
## Installation instructions
Only templates are provided. These will need to be manually copied, so as to have local copies you can edit. These local 
copies will apply to your rig, not the templates.
Copy the 2 following templates files into the same settings folder, by removing the `_template` part of the file name such as 
- `iblrig_settings_template.py` -> `iblrig_settings.py`
- `hardware_settings_template.py` -> `hardware_settings.py`

Those local settings files are git ignored and will not be committed to the repository if you git push on iblrig.
However, when a session is run, the information contained in those setting files will be saved in the raw_behavior_data folder.
