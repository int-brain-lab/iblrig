"""
Choice World Task related logic
"""
from pathlib import Path

import numpy as np

from ibllib.io import session_params
from iblrig.raw_data_loaders import load_task_jsonable
from iblrig.path_helper import load_settings_yaml

CONTRASTS = 1 / np.array([-1, - 2, -4, -8, -16, np.inf, 16, 8, 4, 2, 1])


def _get_latest_training_phase_from_folder(folder_subjects):
    n_retries = 3
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
            trials_data, bpod_data = load_task_jsonable(session_path.joinpath(adt['collection'], '_iblrig_taskData.raw.jsonable'))
            if 'training_phase' in trials_data:
                training_phase = trials_data['training_phase'].values[-1]
                return (training_phase, session_path.parts[-2])
        c += 1
        if c >= n_retries:
            break


def get_training_phase(subject):
    """
    Goes throught the history of a subject and gets the latest training phase for this subject
    :param subject:
    :return:
    """
    DEFAULT_PHASE = 0
    iblrig_settings = load_settings_yaml()
    local_subjects_path = Path(iblrig_settings['iblrig_local_data_path']).joinpath(iblrig_settings['ALYX_LAB'], 'Subjects')
    local = _get_latest_training_phase_from_folder(local_subjects_path.joinpath(subject)) or (DEFAULT_PHASE, '0000-00-00')
    remote = (DEFAULT_PHASE, '0000-00-00')
    if iblrig_settings['iblrig_remote_data_path'] is not None:
        remote_subjects_path = Path(iblrig_settings['iblrig_remote_data_path']).joinpath('Subjects')
        remote = _get_latest_training_phase_from_folder(remote_subjects_path.joinpath(subject)) or (DEFAULT_PHASE, '0000-00-00')
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
