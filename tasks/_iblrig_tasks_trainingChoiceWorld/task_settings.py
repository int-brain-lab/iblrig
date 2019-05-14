# =============================================================================
# TASK PARAMETER DEFINITION (should appear on GUI) init trial objects values
# =============================================================================
# IBL rig root folder
IBLRIG_FOLDER = 'C:\\iblrig'
IBLRIG_DATA_FOLDER = None  # If None data folder will be ..\\iblrig_data from IBLRIG_FOLDER  # noqa
# SOUND, AMBIENT SENSOR, AND VIDEO RECORDINGS
RECORD_SOUND = True
RECORD_AMBIENT_SENSOR_DATA = True
RECORD_VIDEO = True
OPEN_CAMERA_VIEW = True  # if RECORD_VIDEO == True OPEN_CAMERA_VIEW is ignored
# REWARDS
AUTOMATIC_CALIBRATION = True  # Wether to look for a calibration session and func to define the valve opening time  # noqa
CALIBRATION_VALUE = 0.067  # calibration value for 3ul of target reward amount (ignored if automatic ON)  # noqa
REWARD_AMOUNT = 3.  # (µl) Amount of reward to be delivered upon correct choice each trial (overwitten if adaptive ON)  # noqa
REWARD_TYPE = 'Water 10% Sucrose'  # Water, Water 10% Sucrose, Water 15% Sucrose, Water 2% Citric Acid (Guo et al.. PLoS One 2014)  # noqa
# TASK
NTRIALS = 2000  # Number of trials for the current session
USE_AUTOMATIC_STOPPING_CRITERIONS = True  # Weather to check for the Automatic stopping criterions or not  # noqa
USE_VISUAL_STIMULUS = True  # Run the visual stim in bonsai
BONSAI_EDITOR = False  # Whether to open the visual stim Bonsai editor or not
REPEAT_ON_ERROR = True
# STATE TIMERS
QUIESCENCE_THRESHOLDS = [-2, 2]  # degree
QUIESCENT_PERIOD = 0.2  # + x, where x~exp(0.35), t ∈ 0.2 <= R <= 0.5
INTERACTIVE_DELAY = 0.0  # (s) how long after stim onset the CL starts
RESPONSE_WINDOW = 60  # Time to move the wheel after go tone (seconds)
ITI_CORRECT = 1  # how long the stim should stay visible after CORRECT choice
ITI_ERROR = 2  # how long the stim should stay visible after ERROR choice
# VISUAL STIM
STIM_POSITIONS = [-35, 35]  # All possible positions for this session (deg)
STIM_PROBABILITY_LEFT = 0.5
STIM_FREQ = 0.10  # Probably constant - NOT IN USE
STIM_ANGLE = 0.  # Vertical orientation of Gabor patch - NOT IN USE
STIM_SIGMA = 7.  # (azimuth_degree) Size of Gabor patch
STIM_GAIN = 8.  # (azimuth_degree/mm) Gain of the RE to stimulus movement (used if ADAPTIVE_GAIN = FALSE)  # noqa
SYNC_SQUARE_X = 0.95
SYNC_SQUARE_Y = 0.17

# SOUNDS
SOFT_SOUND = 'xonar'  # Use software sound 'xonar', 'sysdefault' or False for BpodSoundCard  # noqa
SOUND_BOARD_BPOD_PORT = 'Serial3'  # (on Bpod) - Ignored if using SOFT_SOUND
WHITE_NOISE_DURATION = 0.5  # Length of noise burst
WHITE_NOISE_AMPLITUDE = 0.05
GO_TONE_DURATION = 0.1  # Length of tone
GO_TONE_FREQUENCY = 5000  # 5KHz
GO_TONE_AMPLITUDE = 0.1  # [0->1]
# ADAPTIVE PARAMETERS
# ADAPTIVE REWARD PARAMETERS (IGNORED IF ADAPTIVE_REWARD = False)
ADAPTIVE_REWARD = True  # wether to increase reware at session start usin AR_* criteria  # noqa
AR_INIT_VALUE = 3  # µl
AR_MIN_VALUE = 1.5  # (µl) 1.5 µl for sugar water, 2 µl for normal water
AR_STEP = 0.1  # µl
AR_CRIT = 200  # number of trials performed
# CONTRASTS
CONTRAST_SET = [1., 0.5, 0.25, 0.125, 0.0625, 0.]  # Full contrast set, used if adaptive contrast = False  # noqa
REPEAT_CONTRASTS = [1., 0.5]  # Contrasts to be repeated if error
# ADAPTIVE_CONTRAST PARAMETERS (IGNORED IF ADAPTIVE_CONTRAST = False)
ADAPTIVE_CONTRAST = True  # Wether to use Adaptive contrast rule or not
AC_INIT_CONTRASTS = [1., 0.5]
AC_BUFFER_SIZE = 50  # Buffer size to compute preformance for each contrast
AC_PERF_CRIT = 0.7  # Criterion for adding next contrast L AND R have to pass
AC_NTRIALS_TO_SIX = 200  # Number of trials after 0.125 to introduce the 6% contrast  # noqa
AC_NTRIALS_TO_ZERO = 400  # Number of trials after 0.125 to introduce the 0% contrast  # noqa
AC_NTRIALS_TO_REMOVE_50 = 600  # Number of trials after 0.125 to remove the 50% contrst  # noqa
# ADAPTIVE_GAIN PARAMETERS (IGNORED IF ADAPTIVE_GAIN = False)
ADAPTIVE_GAIN = True
AG_INIT_VALUE = 8.  # Adaptive Gain init value (azimuth_degree/mm)
AG_MIN_VALUE = 4.  # (azimuth_degree/mm)
# POSITION BIAS FOR REPEATED TRIALS
RESPONSE_BUFFER_LENGTH = 10
# POOP COUNT LOGGING
POOP_COUNT = True  # Wether to ask for a poop count at the end of the session
