"""
Choice World Task related logic
"""
from pathlib import Path

import numpy as np

from ibllib.io import session_params
import iblrig.raw_data_loaders
from iblrig.path_helper import load_settings_yaml

CONTRASTS = 1 / np.array([-1, - 2, -4, -8, -16, np.inf, 16, 8, 4, 2, 1])


def get_adaptive_reward_volume(subject_weight_g, reward_volume_ul, delivered_volume_ul, ntrials):
    """
    If the mouse completed over 200 trials in the previous session, the reward volume is automatically
    lowered by 0.1 microliters for the next session, but cannot go lower than a floor of 1.5 microliters.
    If the mouse received less than its minimum required daily dose (~1 milliliter/25 grams of body weight)
    during the previous session, the reward volume is increased by 0.1 microliters for the next session,
     but cannot go above a ceiling of 3 microliters.
    :param subject_weight_g: in grams
    :param reward_volume_ul: in uL
    :param delivered_volume_ul: in uL
    :param n_trials:
    :return: adaptive_reward_ul
    """
    adaptive_reward_ul = -1
    if subject_weight_g / 25 > reward_volume_ul / 1000:
        adaptive_reward_ul += 0.1
    elif ntrials > 200:
        adaptive_reward_ul -= 0.1
    return adaptive_reward_ul


def _get_latest_training_info_from_folder(folder_subjects):
    """
    Goes throught the history of a subject and gets the latest training phase and the adaptive reward volume for this subject
    :param folder_subjects: the full path to the subjects folder: `Y:/iblrig_data/Subjects/Algernon`
    :return: dict with keys `date`, `training_phase` and `adaptive_reward`
    """
    n_retries = 3  # reads in 3 sessions maximum
    c = 0
    if folder_subjects is None:
        return
    for file_experiment in sorted(folder_subjects.rglob('_ibl_experiment.description*.yaml'), reverse=True):
        session_path = file_experiment.parent
        ad = session_params.read_params(file_experiment)
        if '_iblrig_tasks_trainingChoiceWorld' not in ad['tasks'][0]:
            continue
        for ad_task in ad['tasks']:
            adt = ad_task.get('_iblrig_tasks_trainingChoiceWorld', None)
            if not adt:
                return
            trials_data, bpod_data = iblrig.raw_data_loaders.load_task_jsonable(
                session_path.joinpath(adt['collection'], '_iblrig_taskData.raw.jsonable'))
            if trials_data.shape[0] < 42:  # we consider that under 42 trials it is a dud session
                continue
            task_settings = iblrig.raw_data_loaders.load_settings(session_path, collection=adt['collection'])
            adaptive_reward = get_adaptive_reward_volume(
                subject_weight_g=task_settings['SUBJECT_WEIGHT'],
                reward_volume_ul=task_settings.get('TRAINING_REWARD_AMOUNT_UL', -1),
                delivered_volume_ul=trials_data['reward_amount'].sum(),
                ntrials=trials_data.shape[0])
            if 'training_phase' in trials_data:
                training_phase = trials_data['training_phase'].values[-1]
                return dict(session_path.parts[-2], training_phase=training_phase, adaptive_reward=adaptive_reward)
        c += 1
        if c >= n_retries:
            break


def get_training_info(subject):
    """
    Goes throught the history of a subject and gets the latest training phase for this subject
    :param subject:
    :return:
    """
    DEFAULT_PHASE = 0
    iblrig_settings = load_settings_yaml()
    local_subjects_path = Path(iblrig_settings['iblrig_local_data_path']).joinpath(iblrig_settings['ALYX_LAB'], 'Subjects')
    local = _get_latest_training_info_from_folder(local_subjects_path.joinpath(subject)) or (DEFAULT_PHASE, '0000-00-00')
    remote = (DEFAULT_PHASE, '0000-00-00')
    if iblrig_settings['iblrig_remote_data_path'] is not None:
        remote_subjects_path = Path(iblrig_settings['iblrig_remote_data_path']).joinpath('Subjects')
        remote = _get_latest_training_info_from_folder(remote_subjects_path.joinpath(subject)) or (DEFAULT_PHASE, '0000-00-00')
    if remote[1] > local[1]:
        return remote[0]
    else:
        return local[0]


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
