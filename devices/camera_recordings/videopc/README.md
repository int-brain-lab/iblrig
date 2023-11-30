# To update to this branch 
## **videopc**:
- Delete folder: `C:\iblscripts\deploy\videopc\bonsai`
- `cd C:\iblscripts`
- `conda activate iblenv`
- `git reset --hard`
- `git checkout save_video_test`
- `git pull`
- Go to `C:/iblscripts/deploy/videopc/bonsai/bin/` double-click **setup.bat**
# 
## **ephyspc**:
- Same as above **minus the last step**, no need to setup Bonsai on the ephyspc :)
#
# Desired outcome:
The output we want for these tests will be the count of frames and data entries on the videopc and the count of detected sync pulses from the 3 cameras on the ephyspc.

We're aiming at ~1 hour of video per test.
### videopc:
After finishing the session on the *videopc* a printout should appear in the command line automatically with the required information. 

It should look something like this:

```python
[300, 600, 1500] <-- Video lengths
[300, 600, 1500] <-- Frame Data lengths
```
**Please remember to copy this info!**
### ephyspc:
To get the data from the *ephyspc* you'll have to run a script.
    
  - `cd C:\iblscripts\deploy\ephyspc`
  - `conda activate iblenv`
  - `python ephys_video_lengths.py <INSERT PATH TO SESSION HERE>`
  
If the data was saved in the correct folder and with the correct filenames it should output something like this:

```python
['right_camera: 1500', 'left_camera: 600', 'body_camera: 300']
```
**Please remember to also copy this info!**
#
# **Now for the testing steps**
- Run a `prepare_video_session.py` command as usual for an `_iblrig_test_mouse` subject both on the **videopc** AND the **ephyspc**.

*The behavior will be different from what is currently deployed:*
- Instead of the viewing workflow that was launched before the recording workflow, the rig now launches the setup workflow that has the overlay for the positioning of the cameras.

- After closing the setup workflow on the videopc start the ephys recording system

- The recording workflow will start with blank images as the cameras have their trigger mode ON. You're expected to **MANUALLY turn the trigger mode to OFF (unchecked state)** for all the 3 cameras (more on this below)

- Once the 'session' is done you're expected to **MANUALLY turn the trigger mode back ON (checked state)** for all the 3 cameras 

- Once all the cameras are back in trigger mode you can stop the workflow.
- Stop spikeglx
   
- Copy the values that come out automatically on the video pc and launch the script for the ephyspc. **Note and share these values**.


## Manually turning the trigger mode ON or OFF is done in FlyCapture2
- Open FlyCapture2
- Select one of the cameras
- Click on `Configure Selected` (don't double click on the camera or it will try to open the frame viewer that is already connected to Bonsai)
- Go to `Trigger / Strobe` menu and click/unclick the `Enable / disable trigger`
- Close the configuration menu
- Repeat for all cameras
- Finally, close FlyCapture2 using the window's red 'X' [top right] (NB: if you click OK it will also try to open the viewer as the last camera is still selected)
#
## **Bonus test to simplify your life**
Now, I know manually triggering/untriggering all the cameras is annoying so I created a script to "semi-manually" do the same thing. It would

Once you get to the MANUAL part of triggering untriggering, instead of doing that:
- Open another anaconda prompt
- `conda activate iblenv`
- `cd C:\iblscripts\deploy\videopc`
- Run: `python .\config_cameras.py --disable_trig` (instead of manually turning OFF the triggers of all the cameras)
- Before stopping the workflow run: `python .\config_cameras.py --enable_trig` (to do the opposite)
- Copy and share the output in the prompt after this also.
#
# To go back to previous version
- Delete folder: `C:\iblscripts\deploy\videopc\bonsai`
- `cd C:\iblscripts`
- `git reset --hard`
- `git checkout master`
- `git pull`
- Go to `C:/iblscripts/deploy/videopc/bonsai/bin/` doubleclick on **Bonsai64.exe**
# 
# 
# 
# 
# (IGNORE FOR NOW) UPDATE spinnaker-python and iblenv to python 3.7
- Download `spinnaker_python-2.3.0.77-cp37-cp37m-win_amd64.whl` file to your **DOWNLOADS** folder
from [**HERE**](https://drive.google.com/file/d/1-voz7KN2jD_njjQ8Y2CLqQBGO461HLB_/view?usp=sharing)
- `conda env remove -y -n iblenv`
- `conda create -y -n iblenv python=3.7`
- `conda activate iblenv`
- `pip install ibllib`
- `pip install ~\Downloads\spinnaker_python-1.20.0.15-cp36-cp36m-win_amd64.whl`
- `conda install -y git`
# 
