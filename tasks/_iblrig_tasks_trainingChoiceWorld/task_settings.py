# =============================================================================
# TASK PARAMETER DEFINITION (should appear on GUI) init trial objects values
# =============================================================================
# ROTARY ENCODER
ROTARY_ENCODER_PORT = 'COM4'
# OSC
OSC_CLIENT_PORT = 7110
OSC_CLIENT_IP = '127.0.0.1'
# IBL rig root folder
IBLRIG_FOLDER = 'C:\\iblrig'
MAIN_DATA_FOLDER = None  # If None data folder will be C:\\iblrig_data\\Subjects
# SOUND, AMBIENT SENSOR, AND VIDEO RECORDINGS
RECORD_SOUND = True
RECORD_AMBIENT_SENSOR_DATA = True
RECORD_VIDEO = True
# TASK
NTRIALS = 1000  # Number of trials for the current session
USE_VISUAL_STIMULUS = True  # Run the visual stim in bonsai
BONSAI_EDITOR = False  # Whether to open the Bonsai editor or not
CONTRAST_SET = [1., 0.5, 0.25, 0.125, 0.0625, 0.]  # Full contrast set, used if adaptive contrast = False
REPEAT_ON_ERROR = True
REPEAT_CONTRASTS = [1., 0.5]
# STATE TIMERS
QUIESCENCE_THRESHOLDS = [-2, 2]  # degree
QUIESCENT_PERIOD = 0.2  # + x, where x~exp(0.35), t ∈ 0.2 <= R <= 0.5
INTERACTIVE_DELAY = 0.1  # how long after stim onset the CL starts
RESPONSE_WINDOW = 60  # Time to move the wheel after go tone (seconds)
ITI_CORRECT = 1  # how long the stim should stay visible after CORRECT choice
ITI_ERROR = 2  # how long the stim should stay visible after ERROR choice
# ADAPTIVE PARAMETERS
ADAPTIVE_REWARD = True  # wether to increase reware at session start usin AR_* criteria
ADAPTIVE_CONTRAST = True  # MAKE FIXED_CONTRAST OBJECT, swap at init if this is false
ADAPTIVE_GAIN = True
# REWARDS
AUTOMATIC_CALIBRATION = True  # Wether to look for a calibration session and func to define the valve opening time
CALIBRATION_VALUE = 0.067  # calibration value for 3ul of target reward amount (ignored if automatic ON)
REWARD_AMOUNT = 3.  # (µl) Amount of reward to be delivered upon correct choice each trial (overwitten if adaptive ON)
# Water, Water 10% Sucrose, Water 15% Sucrose, Water 2% Citric Acid (Guo et al.. PLoS One 2014)
REWARD_TYPE = 'Water'
# ADAPTIVE REWARD PARAMETERS (IGNORED IF ADAPTIVE_REWARD = False)
AR_INIT_VALUE = 3  # µl
AR_MIN_VALUE = 2  # µl
AR_STEP = 0.1  # µl
AR_CRIT = 200  # number of trials performed
# ADAPTIVE_CONTRAST PARAMETERS (IGNORED IF ADAPTIVE_CONTRAST = False)
AC_INIT_CONTRASTS = [1., 0.5]  # All possible contrasts [1., 0.5, 0.25, 0.125, 0.0625, 0.]
AC_BUFFER_SIZE = 50
AC_PERF_CRIT_ONE = 0.7  # Criterion for adding next contrast L AND R have to pass
AC_PERF_CRIT_TWO = 0.65  # Criterion for contrast 0.0625
AC_NTRIALS_TO_ZERO = 200  # Number of trials after 0.125 required to introduce the 0. contrast
# VISUAL STIM
STIM_POSITIONS = [-35, 35]  # All possible positions for this session (deg)
STIM_PROBABILITY_LEFT = 0.5
STIM_FREQ = 0.10  # Probably constant - NOT IN USE
STIM_ANGLE = 0.  # Vertical orientation of Gabor patch - NOT IN USE
STIM_SIGMA = 7.  # (azimuth_degree) Size of Gabor patch
STIM_GAIN = 8.  # (azimuth_degree/mm) Gain of the RE to stimulus movement (used if ADAPTIVE_GAIN = FALSE)
# ADAPTIVE_GAIN PARAMETERS (IGNORED IF ADAPTIVE_GAIN = False)
AG_INIT_VALUE = 8.  # Adaptive Gain init value (azimuth_degree/mm)
AG_MIN_VALUE = 4.  # (azimuth_degree/mm)
# SOUNDS
SOFT_SOUND = 'xonar'  # Use software sound 'xonar', 'sysdefault' or False for BpodSoundCard
SOUND_BOARD_BPOD_PORT = 'Serial3'  # (on Bpod) - Ignored if using SOFT_SOUND
WHITE_NOISE_DURATION = 0.5  # Length of noise burst
WHITE_NOISE_AMPLITUDE = 0.05
GO_TONE_DURATION = 0.1  # Length of tone
GO_TONE_FREQUENCY = 5000  # 5KHz
GO_TONE_AMPLITUDE = 0.1  # [0->1]
# POSITION BIAS
TRAINED = False
RESPONSE_BUFFER_LENGTH = 10
