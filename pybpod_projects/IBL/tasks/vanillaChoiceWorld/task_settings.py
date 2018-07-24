# =============================================================================
# TASK PARAMETER DEFINITION (should appear on GUI) init trial objects values
# =============================================================================
# Stuff that should come from PyBpod
PROJECT = 'IBL'
TASK = 'vanillaChoiceWorld'
BOX = 'Box0'
MOUSE_NAME = '4577'  # CHANGE THIS!!!!
EXPERIMENTER = 'IL'
ROTARY_ENCODER_PORT = 'COM3'
ROTARY_ENCODER_SERIAL_PORT_NUM = 1
OSC_CLIENT_PORT = 7110
OSC_CLIENT_IP = '127.0.0.1'
# ROOT_DATA_FOLDER = None -> relative path in  ../pybpod_projects/IBL/data/
ROOT_DATA_FOLDER = None
# TASK
NTRIALS = 1000  # Number of trials for the current session
USE_VISUAL_STIMULUS = True  # Run the visual stim in bonsai
REPEAT_ON_ERROR = True
REPEAT_STIMS = [1., 0.5]
# REWARDS
TARGET_REWARD = 3  # in µl
CALIBRATION_VALUE = 0.0672  # calibrated to 1µl on 2018-01-19
# STATE TIMERS
QUIESCENT_PERIOD = 0.5  # Trial init (quiescent period) enforced
QUIESCENCE_THRESHOLDS = [-2, 2]  # degree
INTERACTIVE_DELAY = 0.5  # how long after stim onset the CL starts
RESPONSE_WINDOW = 0  # Time to move the wheel after go tone (0 for inf)
ITI_CORRECT = 1  # how long the stim should stay visible after CORRECT choice
ITI_ERROR = 2  # how long the stim should stay visible after ERROR choice
# VISUAL STIM
STIM_POSITIONS = [-90, 90]  # All possible positions for this session
STIM_CONTRASTS = [1., 0.5, 0.25, 0.125, 0.0625, 0.]  # All possible contrasts
STIM_FREQ = 0.19  # Probably constant - NOT IN USE
STIM_ANGLE = 0.  # Vertical orientation of Gabor patch - NOT IN USE
STIM_SIGMA = 9.  # (azimuth_degree) Size of Gabor patch
# Not adaptive_contrast on a trial be trial basis
STIM_GAIN = 5.  # (azimuth_degree/mm) Gain of the RE to stimulus movement
# SOUNDS
SOUND_SAMPLE_FREQ = 44100  # 192000  # depends on the sound card. 96000 ?
WHITE_NOISE_DURATION = ITI_ERROR  # Length of noise burst
WHITE_NOISE_AMPLITUDE = 0.05
GO_TONE_DURATION = 0.1  # Length of tone
GO_TONE_FREQUENCY = 8000  # 10KHz
GO_TONE_AMPLITUDE = 0.2  # [0->1]
# STAIRCASE_CONTRAST TRIALS
ST_CONTRAST = 1.
ST_FREQ = 2
ST_HIT_THRESH = 3
ST_MISS_THRESH = 1
# ADAPTIVE_CONTRAST TRIALS
AT_BUFFER_SIZE = 50
