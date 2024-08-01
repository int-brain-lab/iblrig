"""
Choice World Task related logic and functions that translate the task description in
Appendix 2 of the paper into code.
"""

import logging
from typing import Literal

import numpy as np

import iblrig.raw_data_loaders
from iblrig.path_helper import iterate_previous_sessions

log = logging.getLogger(__name__)

CONTRASTS = 1 / np.array([-1, -2, -4, -8, -16, np.inf, 16, 8, 4, 2, 1])
DEFAULT_TRAINING_PHASE = 0
DEFAULT_REWARD_VOLUME = 3.0


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
    subject_name: str,
    task_name: str = '_iblrig_tasks_trainingChoiceWorld',
    stim_gain: float | None = None,
    stim_gain_on_error: float | None = None,
    default_reward: float = DEFAULT_REWARD_VOLUME,
    mode: Literal['silent', 'raise'] = 'silent',
    **kwargs,
) -> tuple[dict, dict | None]:
    """
    Goes through a subject's history and gets the latest training phase and adaptive reward volume.

    Parameters
    ----------
    subject_name : str
        Name of the subject.
    task_name : str, optional
        Name of the protocol to look for in experiment description, defaults to '_iblrig_tasks_trainingChoiceWorld'.
    stim_gain: float, optional
        Default stimulus gain if no previous session is available, default to None
    stim_gain_on_error: float, optional
        Default stimulus gain if there was an exception whilst obtaining the previous sessions's info, default to None
    default_reward : float, optional
        Default reward volume in uL if no previous session is available.
    mode : str, optional
        If 'silent' returns default values if no history is found, if 'raise' raises ValueError.
    **kwargs
        Optional arguments to be passed to get_local_and_remote_paths

    Returns
    -------
    training_info: dict
        Dictionary with keys: training_phase, adaptive_reward, adaptive_gain
    session_info: dict or None
        Dictionary with keys: session_path, experiment_description, task_settings, file_task_data
    """

    # default values (if no previous session is available)
    training_info = {
        'training_phase': DEFAULT_TRAINING_PHASE,
        'adaptive_reward': default_reward,
        'adaptive_gain': stim_gain,
    }

    # try to obtain the subject's previous session's info
    try:
        session_info = iterate_previous_sessions(subject_name, task_name=task_name, n=1, **kwargs)
        if len(session_info) > 0:
            session_info = session_info[0]
            task_settings = session_info.get('task_settings')
            trials_data, _ = iblrig.raw_data_loaders.load_task_jsonable(session_info.get('file_task_data'))
    except Exception as e:
        log.exception(msg='Error obtaining training information from previous session!', exc_info=e)
        training_info['adaptive_gain'] = stim_gain_on_error
        session_info = []

    # handle lack of previous sessions
    if len(session_info) == 0:
        if mode == 'silent':
            log.warning(
                f"Could not determine training status for subject '{subject_name}' - returning default values "
                f'(training phase: {training_info["training_phase"]}, adaptive reward: '
                f'{training_info["adaptive_reward"]:.1f} μL, adaptive gain: {training_info["adaptive_gain"]})'
            )
            return training_info, None
        else:
            raise ValueError(f'The training status for {subject_name} could not be determined as no previous sessions were found')

    # compute reward volume from previous session
    prev_reward_vol = task_settings.get('ADAPTIVE_REWARD_AMOUNT_UL') or task_settings.get('REWARD_AMOUNT_UL')
    training_info['adaptive_reward'] = compute_adaptive_reward_volume(
        subject_weight_g=task_settings.get('SUBJECT_WEIGHT'),
        reward_volume_ul=prev_reward_vol,
        delivered_volume_ul=trials_data.get('reward_amount').sum(),
        ntrials=trials_data.shape[0],
    )

    # retrieve training_phase from the previous session's trials table
    if 'training_phase' in trials_data:
        training_info['training_phase'] = trials_data['training_phase'].values[-1]

    # set adaptive gain depending on number of correct trials in previous session
    if np.sum(trials_data['response_side'] != 0) > 200:
        training_info['adaptive_gain'] = task_settings.get('STIM_GAIN')
    else:
        training_info['adaptive_gain'] = task_settings.get('ADAPTIVE_GAIN_VALUE', task_settings.get('AG_INIT_VALUE'))

    return training_info, session_info


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


def draw_training_contrast(phase: int) -> float:
    probabilities = training_contrasts_probabilities(phase)
    return np.random.choice(CONTRASTS, p=probabilities)


def contrasts_set(phase: int) -> np.array:
    probabilities = training_contrasts_probabilities(phase)
    return CONTRASTS[probabilities > 0]


def training_phase_from_contrast_set(contrast_set: list[float]) -> int | None:
    contrast_set = sorted(contrast_set)
    for phase in range(6):
        expected_set = CONTRASTS[np.logical_and(training_contrasts_probabilities(phase) > 0, CONTRASTS >= 0)]
        if np.array_equal(contrast_set, expected_set):
            return phase
    raise Exception(f'Could not determine training phase from contrast set {contrast_set}')
