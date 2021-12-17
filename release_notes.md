# **Release notes**

## **Release Notes 6.5.3**

- Removed botched releases and patched release notes accordingly.
- RECAP: New bootstrapper and OLD stimulus file i.e.:
  - Bonvision 0.9.0
  - All other Bonsai packages to latest
  - Removed reverse contingencies capabilities
  - Removed assurance stim stops in the center of the screen
  - Added STIMCENTER capabilities for habituationCW compatibility and bpod override for testing
  - Changed Last to Take 1 node at top level workflow of main stim file

## **Release Notes ~~6.5.2~~**

- Bugfix: avoid code copy in HabituationCW and TrainingCW on ephys rig
- Bugfix: avoid shader window freezing Bonsai processing: Keep latest bootstrapper, downgraded shader package/Bonvision

## **Release Notes ~~6.5.1~~**

- Exposed Spontaneous activity timer to task code so users can change it if they want.
- Small Bugfix in copy task code routine for personal projects, now consideres the project folder
- Bugfix introduced by pandas syntax change in water calibration
- Removed maxval of 12 for selection of pregenerated sessions in pop up prompt
- Reversed double and single quote in install for ONE install procedure
- Updated Bonsai.Design.Visualizers" version="2.6.2
- Some refactoring of session_creator.py in preparation of full session creation on task startup
- ~~Removed Merge and Repeat node encapsulation of Bonsai state machine in visual stim~~
- Added disabled node with rollback of closed_loop state in Bonsai visual stim workflow
- Bugfix: Training/HabituationCW video folder now not created on ephys rig
- Added logging and traceback to create_session.py and register_session.py PR#370
- Fixed a move_passive bug

## **Release Notes ~~6.5.0~~**

- Added camera config script == videopc
- Added CI builds for windows/ubuntu install
- Optimized and fixed broken install procedure
- Added script for calculation of wheel to screen positions
- Added script for getting screen positions from wheel input (postprocessing)
- Separated local param methods from Alyx board methods usning alyx module
- Added tests for param module and path helper object
- Created method for finding mapped network drives on local rigs
- Added local and remote data folder to params_alyx
- Swapped training camera timestamps/bonsai timestamps
- Added backup params file on write
- Added register_screen_lux script
- Transfer data will attempt to move all passive session that it finds before starting
- ~~Fixed stimulus overshooting/undershooting on center or right/left thresholds~~
- Updated Bonsai and packages
- ~~Added stimulus capability for reverse contingencies~~
- Updated Bonsai deployment methods
- Removed all ONE calls from task launching procedures
- Added sonic studio config file for xonar sound card config (in iblrig/devices/sound_card/IBL.nsx2)
- HabituationCW now uses IBL default stimulus
- Fixed bug in camera recording where SAVE_VIDEO = False would make stream not start (deprecated task settings SAVE_VIDEO flag)
- Added bonsai.show_stim method to BpodMessageCreator obj
- Deprecated RECORD_VIDEO "knob"
- Exposed rate of passive stimulation workflow defaults to 0.1
- Refactored update with \_update, and git module
- Added create_custom_project CLI for syncing pybpod w/ Alyx project/users/subjects
- move_passive will now try/catch to move all possible sessions
- Migrated to ONE2
- ~~Bugfixed visual stim BpodEvents now not sampled on render frame~~
- Changed install and setup procedures
- Added mamba dependency to conda environment
- Added updating of conda and base python pip wheel and setuptools, clearing cona cache before install
- Install procedure now deletes Bonsai folder if it exists and Bonsai setup
- Fixed version of python to 3.7.11
- Created new ibllib 'hidden' environment just to do ONE2 tasks install and update methods updated
- Launching pybpod will now not try to update update procedures
- Created envs.py module to deal with environment related juggling for launching different scripts in different contexts
- ONE/ibllib still installed in iblenv but ready to be removed for next release

## **Release Notes 6.4.2**

Patch update (bugfixes)

- Increased stim_off state timer to 150ms
- Updated ibllib, Bonsai and Bonvision
- New update procedure for Bonsai that will simplify updates for users
- New pipeline architecture (removed deprecated flag creations on transfer)
- Mice that have more than one project now will require user to pick the project on run
- Stimulus phase fix for ephys choice world pre generated sessions
- Added tests for path_helper, adaptive module (for trainingCW) , and init alyx module tests

## **Release Notes 6.4.1**

Patch update (bugfixes)

- Increased stim_on state timer to 150ms
- Added write timeout to frame2TTL serial connecion
- Added screen frequency target to rig params
- Fixed bug in passive ChoiceWorld

## **Release Notes 6.4.0**

Minor update (added features)

- Added saving of \_iblrig_syncSquareUpdate.raw.csv from bonsai visual stim
- updaed ibllib to 1.4.11
- updated pybpod
- updated Bonsai
- increased spontaneous activity period to 10 min in passiveChoiceWorld
- Stop microphone recordings after passive protocol

## **Release Notes 6.3.1**

Patch update (bugfixes)

- Saving now data from Bonsai for frame2TL freq test

## **Release Notes 6.3.0**

Minor update (added functionality)

- Created \_iblrig_misc_frame2TTL_freq_test / test task for screen/frame2TTL
- Added sound recording in ephys rig for both biased and ephysCW tasks (was missing)

## **Release Notes 6.2.5**

_THIS: State Machine changed_
Patch update (bugfixes)

- Fixed stimulus sometimes keeps moving after reward for all tasks
- Fixed session_params bug in ephysCW
- Under the hood refactorings

## **Release Notes 6.2.4**

Patch update (bugfixes)

- Fixed missing underscore in move passive
- Fixed missing poop_count.py file in scripts folder
- Added popup window to warn to close valve on passiveCW launch
- Bugfix in sph.display_logs() that made SPH crash if no previous session was found.
- Updated ibllib to 1.3.10

## **Release Notes 6.2.3**

Patch update (bugfixes)

- Minor optimization to path_helper
- Rename of session at end of passive now includes corresponding ephys session

## **Release Notes 6.2.2**

Patch update (bugfixes)

- SESSION_ORDER bugfix

## **Release Notes 6.2.1**

Patch update (bugfixes)
Mainly in **ephysCW** and **passiveCW**

- Poop only at end o passive run
- Refactored ask_mock logic
- Bugfixed ask_mock where pressing cancel would crash the UI
- Removed confirmation of session number to load on passive Launch

## **Release Notes 6.2.0**

Minor update (added functionality)

- Updated ibllib
- **ephys_certification** protocol:
  - Updated metadata
  - Terminal output to inform users stim has started
- New datasetType that saves timestamp and position of visual stim from Bonsai (All tasks but habituationCW)
- **ephysChoiceWorld** mock protocol implemetation
- **passiveChoiceWorld** released for testing
- Created release_notes.md file
