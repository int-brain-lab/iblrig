# =============================================================================
# TASK PARAMETER DEFINITION (should appear on GUI) init trial objects values
# =============================================================================
# ROTARY ENCODER
ROTARY_ENCODER_PORT = 'COM3'
# OSC
OSC_CLIENT_PORT = 7110
OSC_CLIENT_IP = '127.0.0.1'
# IBL rig root folder
IBLRIG_FOLDER = 'C:\\iblrig'
MAIN_DATA_FOLDER = None  # If None data folder will be C:\\ibldata\\Subjects
RECORD_SOUND = True
RECORD_AMBIENT_SENSOR_DATA = True
# TASK
NTRIALS = 1000  # Number of trials for the current session
USE_VISUAL_STIMULUS = True  # Run the visual stim in bonsai
BONSAI_EDITOR = False  # Whether to open the Bonsai editor or not
REPEAT_ON_ERROR = True
REPEAT_STIMS = [1., 0.5]
# REWARDS
REWARD_INIT_VALUE = 3  # µl
REWARD_MIN_VALUE = 2  # µl
REWARD_STEP = 0.1  # µl
REWARD_CRIT = 200  # number of trials performed
CALIBRATION_VALUE = 0.067  # calibrated to 1µl on 2018-05-10
# STATE TIMERS
QUIESCENT_PERIOD = 0.5  # Trial init (quiescent period) enforced
QUIESCENCE_THRESHOLDS = [-2, 2]  # degree
INTERACTIVE_DELAY = 0.5  # how long after stim onset the CL starts
RESPONSE_WINDOW = 3600  # Time to move the wheel after go tone (seconds)
ITI_CORRECT = 1  # how long the stim should stay visible after CORRECT choice
ITI_ERROR = 2  # how long the stim should stay visible after ERROR choice
# VISUAL STIM
STIM_POSITIONS = [-35, 35]  # All possible positions for this session
STIM_CONTRASTS = [1., 0.5, 0.25, 0.125, 0.0625, 0.]  # All possible contrasts
STIM_FREQ = 0.19  # Probably constant - NOT IN USE
STIM_ANGLE = 0.  # Vertical orientation of Gabor patch - NOT IN USE
STIM_SIGMA = 9.  # (azimuth_degree) Size of Gabor patch
STIM_GAIN = 5.  # (azimuth_degree/mm) Gain of the RE to stimulus movement
# SOUNDS
SOFT_SOUND = 'onboard'  # Use software sound 'xonar', 'onboard' or False for BpodSoundCard
# Moule port where the SoundBoard is connected (ignored if using software sound)
SOUND_BOARD_BPOD_PORT = 'Serial3'
WHITE_NOISE_DURATION = ITI_ERROR  # Length of noise burst
WHITE_NOISE_AMPLITUDE = 0.05
GO_TONE_DURATION = 0.1  # Length of tone
GO_TONE_FREQUENCY = 10000  # 10KHz
GO_TONE_AMPLITUDE = 0.5  # [0->1]
# STAIRCASE_CONTRAST TRIALS
ST_CONTRAST = 1.
ST_FREQ = 2
ST_HIT_THRESH = 3
ST_MISS_THRESH = 1
# ADAPTIVE_CONTRAST TRIALS
AT_BUFFER_SIZE = 50
