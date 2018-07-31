# =============================================================================
# TASK SETTINGS DEFINITION (should appear on GUI)
# =============================================================================
# Stuff that should come from PyBpod
PROJECT = 'IBL'
TASK = 'advancedChoiceWorld'
BOX = 'Box0'
MOUSE_NAME = 'aCW_test_mouse'
EXPERIMENTER = 'Nico'
ROTARY_ENCODER_PORT = 'COM3'
ROTARY_ENCODER_SERIAL_PORT_NUM = 1
OSC_CLIENT_PORT = 7110
OSC_CLIENT_IP = '127.0.0.1'
# ROOT_DATA_FOLDER = None -> relative path in  ../pybpod_projects/IBL/data/
ROOT_DATA_FOLDER = None
# TASK
NTRIALS = 10  # Number of trials for the current session
USE_VISUAL_STIMULUS = True  # Run the visual stim in bonsai
REPEAT_ON_ERROR = True
REPEAT_STIMS = [1., 0.5]
# REWARDS
VALVE_TIME = 0.2016  # calibrated on 2018-01-19
# STATE TIMERS
RESPONSE_WINDOW = 0  # 0 for inf timer of state set to 0 means non existant
INTERACTIVE_DELAY = 0.5  # how long after stim onset the CL starts
ITI = 0.5  # Inter trial delay happens every trial
ITI_CORRECT = 1  # how long the stim should stay visible after CORRECT choice
ITI_ERROR = 2  # # how long the stim should stay visible after ERROR choice
# VISUAL STIM
STIM_POSITIONS = [-90, 90]  # All possible positions for this session
STIM_CONTRASTS = [1., 0.5, 0.25, 0.125, 0.0625, 0.]  # All possible contrasts
STIM_FREQ = 0.2  # Probably constant
STIM_ANGLE = 0.  # Vertical orientation of Gabor patch (0=vertical)
STIM_SIGMA = 20.  # Size of the gabor patch gaussian window
# Not adaptive on a trial be trial basis
STIM_GAIN = 5.  # Gain of the RE to stimulus movement
# SOUNDS
SOUND_SAMPLE_FREQ = 44100  # 192000  # depends on the sound card. 96000 ?
WHITE_NOISE_DURATION = ITI_ERROR  # Length of noise burst
WHITE_NOISE_AMPLITUDE = 0.05
GO_TONE_DURATION = 0.1  # Length of tone
GO_TONE_FREQUENCY = 10000  # 10KHz
GO_TONE_AMPLITUDE = 1  # [0->1]
