from one.registration import RegistrationClient


def register_session(session_path, settings_dict, one=None):
    """Register session in Alyx database.
    """
    if one is None:
        return
    registration_kwargs = {
        'ses_path': session_path,
        'file_list': False,
        'users': [settings_dict['ALYX_USER']],
        'location': settings_dict['RIG_NAME'],
        'procedures': settings_dict['PROCEDURES'],
        'n_correct_trials': settings_dict['NTRIALS_CORRECT'],
        'n_trials': settings_dict['NTRIALS'],
        'projects': settings_dict['PROJECTS'],
        'task_protocol': settings_dict['PYBPOD_PROTOCOL'],
        'lab': settings_dict['ALYX_LAB'],
        'start_time': settings_dict['SESSION_START_TIME'],
        'end_time': settings_dict['SESSION_END_TIME']
    }
    rc = RegistrationClient(one=one)
    rc.register_session(**registration_kwargs)





