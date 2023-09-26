"""
Choice World Task related logic and functions that translate the task description in
Appendix 3 of the paper into code.
"""

import numpy as np

import iblrig.raw_data_loaders
from iblrig.path_helper import iterate_previous_sessions

CONTRASTS = 1 / np.array([-1, - 2, -4, -8, -16, np.inf, 16, 8, 4, 2, 1])
DEFAULT_TRAINING_PHASE = 0
DEFAULT_REWARD_VOLUME = 3


def compute_adaptive_reward_volume(subject_weight_g, reward_volume_ul, delivered_volume_ul, ntrials):
    """
    If the mouse completed over 200 trials in the previous session, the reward volume is automatically
    lowered by 0.1 microliters for the next session, but cannot go lower than a floor of 1.5 microliters.
    If the mouse received less than its minimum required daily dose (~1 milliliter/25 grams of body weight)
    during the previous session, the reward volume is increased by 0.1 microliters for the next session,
     but cannot go above a ceiling of 3 microliters.
    :param subject_weight_g: in grams
    :param reward_volume_ul: the last reward volume setting in uL
    :param delivered_volume_ul: the cumulative water deliverd during the last session in uL
    :param n_trials:
    :return: adaptive_reward_ul
    """
    if subject_weight_g > (delivered_volume_ul / 1000 * 25):
        reward_volume_ul += 0.1
    elif ntrials > 200:
        reward_volume_ul -= 0.1
    return np.maximum(np.minimum(reward_volume_ul, 3), 1.5)


def get_subject_training_info(
        subject_name, subject_weight_grams=None, task_name='_iblrig_tasks_trainingChoiceWorld',
        default_reward=DEFAULT_REWARD_VOLUME, mode='silent', **kwargs):
    """
    Goes through the history of a subject and gets the latest
    training phase and the adaptive reward volume for this subject
    :param subject_name:
    :param subject_weight_grams: current weight of the subject in grams, if not available, will use the previous session weight
    :param default_reward: default reward volume in uL if no previous session is available
    :param task_name: name of the protocol to look for in experiment description,
     defaults to '_iblrig_tasks_trainingChoiceWorld'
    :param mode: 'defaults' or 'raise': if 'defaults' returns default values if no history is found, if 'raise' raises ValueError
    :param **kwargs: optional arguments to be passed to iblrig.path_helper.get_local_and_remote_paths
    if not used, will use the arguments from iblrig/settings/iblrig_settings.yaml
    :return:
    """
    session_info = iterate_previous_sessions(subject_name, task_name=task_name, n=1, **kwargs)
    if len(session_info) == 0:
        if mode == 'silent':
            return DEFAULT_TRAINING_PHASE, default_reward
        elif mode == 'raise':
            raise ValueError("The training status could not be determined as no previous sessions were found")
    else:
        session_info = session_info[0]
    trials_data, _ = iblrig.raw_data_loaders.load_task_jsonable(session_info.file_task_data)
    previous_reward_volume = (session_info.task_settings.get('ADAPTIVE_REWARD_AMOUNT_UL') or
                              session_info.task_settings.get('REWARD_AMOUNT_UL'))
    adaptive_reward = compute_adaptive_reward_volume(
        subject_weight_g=subject_weight_grams or session_info.task_settings['SUBJECT_WEIGHT'],
        reward_volume_ul=previous_reward_volume,
        delivered_volume_ul=trials_data['reward_amount'].sum(),
        ntrials=trials_data.shape[0])
    if 'training_phase' in trials_data:
        training_phase = trials_data['training_phase'].values[-1]
    else:
        training_phase = DEFAULT_TRAINING_PHASE
    return training_phase, adaptive_reward


def training_contrasts_probabilities(phase=1):
    match phase:
        case 0:  # Starts with only 100% and 50% contrasts.
            frequencies = np.abs(CONTRASTS) >= 0.5
        case 1:  # The 25% contrast is added to the set.
            frequencies = np.abs(CONTRASTS) >= 0.25
        case 2:  # The 12.5% contrast is added to the set.
            frequencies = np.abs(CONTRASTS) >= 0.125
        case 3:  # The 6.25% contrast is added to the set.
            frequencies = np.abs(CONTRASTS) >= 0.0625
        case 4:  # The 0% contrast is added to the set.
            frequencies = np.abs(CONTRASTS) >= 0
        case 5:  # The 50% contrast is removed from the set
            frequencies = np.abs(CONTRASTS) != 0.5
    return frequencies / np.sum(frequencies)


def draw_training_contrast(phase):
    probabilities = training_contrasts_probabilities(phase)
    return np.random.choice(CONTRASTS, p=probabilities)


def contrasts_set(phase):
    probabilities = training_contrasts_probabilities(phase)
    return CONTRASTS[probabilities > 0]
