# **Release notes**

## **Release Notes 6.4.0**

Minor update (added features)

* Added saving of _iblrig_syncSquareUpdate.raw.csv from bonsai visual stim
* updaed ibllib to 1.4.11
* updated pybpod
* updated Bonsai
* increased spontaneous activity period to 10 min in passiveChoiceWorld
* Stop microphone recordings after passive protocol

## **Release Notes 6.3.1**

Patch update (bugfixes)

* Saving now data from Bonsai for frame2TL freq test

## **Release Notes 6.3.0**

Minor update (added functionality)

* Created _iblrig_misc_frame2TTL_freq_test / test task for screen/frame2TTL
* Added sound recording in ephys rig for both biased and ephysCW tasks (was missing)

## **Release Notes 6.2.5**
*THIS: State Machine changed*
Patch update (bugfixes)  

* Fixed stimulus sometimes keeps moving after reward for all tasks
* Fixed session_params bug in ephysCW
* Under the hood refactorings
  
## **Release Notes 6.2.4**

Patch update (bugfixes)

* Fixed missing underscore in move passive
* Fixed missing poop_count.py file in scripts folder
* Added popup window to warn to close valve on passiveCW launch
* Bugfix in sph.display_logs() that made SPH crash if no previous session was found.
* Updated ibllib to 1.3.10

## **Release Notes 6.2.3**

Patch update (bugfixes)

* Minor optimization to path_helper
* Rename of session at end of passive now includes corresponding ephys session

## **Release Notes 6.2.2**

Patch update (bugfixes)  

* SESSION_ORDER bugfix

## **Release Notes 6.2.1**

Patch update (bugfixes)  
Mainly in **ephysCW** and **passiveCW**

* Poop only at end o passive run
* Refactored ask_mock logic
* Bugfixed ask_mock where pressing cancel would crash the UI
* Removed confirmation of session number to load on passive Launch

## **Release Notes 6.2.0**

Minor update (added functionality)

* Updated ibllib
* **ephys_certification** protocol:
  * Updated metadata
  * Terminal output to inform users stim has started
* New datasetType that saves timestamp and position of visual stim from Bonsai (All tasks but habituationCW)
* **ephysChoiceWorld** mock protocol implemetation
* **passiveChoiceWorld** released for testing
* Created release_notes.md file
