# **Release notes**

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
