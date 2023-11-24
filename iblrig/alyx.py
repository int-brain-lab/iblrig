import iblrig
from iblutil.util import setup_logger
from one.registration import RegistrationClient

log = setup_logger('iblrig')


def register_session(session_path, settings_dict, one=None):
    """Register session in Alyx database."""

    if one is None:
        return

    def ensure_list(x):
        x = [] if x is None else x
        return x if isinstance(x, list) else [x]

    registration_kwargs = {
        'ses_path': session_path,
        'file_list': False,
        'users': [settings_dict['ALYX_USER'] or one.alyx._par.ALYX_LOGIN],
        'location': settings_dict['RIG_NAME'],
        'procedures': ensure_list(settings_dict['PROCEDURES']),
        'n_correct_trials': settings_dict['NTRIALS_CORRECT'],
        'n_trials': settings_dict['NTRIALS'],
        'projects': ensure_list(settings_dict['PROJECTS']),
        'task_protocol': settings_dict['PYBPOD_PROTOCOL'] + iblrig.__version__,
        'lab': settings_dict['ALYX_LAB'],
        'start_time': settings_dict['SESSION_START_TIME'],
        'end_time': settings_dict['SESSION_END_TIME'],
    }
    rc = RegistrationClient(one=one)
    ses, _ = rc.register_session(**registration_kwargs)
    log.info(f'session registered in Alyx database: {ses["subject"]}, {ses["start_time"]}, {ses["number"]}')

    # add the weight if available and if there is no previous weighing registered
    if settings_dict['SUBJECT_WEIGHT']:
        wd = dict(nickname=settings_dict['SUBJECT_NAME'], date_time=settings_dict['SESSION_START_TIME'])
        previous_weighings = one.alyx.rest('weighings', 'list', **wd, no_cache=True)
        if len(previous_weighings) == 0:
            wd = dict(
                subject=settings_dict['SUBJECT_NAME'],
                date_time=settings_dict['SESSION_START_TIME'],
                weight=settings_dict['SUBJECT_WEIGHT'],
            )
            one.alyx.rest('weighings', 'create', data=wd)
            log.info(f"weighing registered in Alyx database: {ses['subject']}, {settings_dict['SUBJECT_WEIGHT']}g")

    # add the water administration if there is no water administration registered
    if settings_dict['TOTAL_WATER_DELIVERED']:
        if len(one.alyx.rest('water-administrations', 'list', session=ses['url'][-36:], no_cache=True)) == 0:
            wa_data = dict(
                session=ses['url'][-36:],
                subject=settings_dict['SUBJECT_NAME'],
                water_type=settings_dict.get('REWARD_TYPE', None),
                water_administered=settings_dict['TOTAL_WATER_DELIVERED'] / 1000,
            )
            one.alyx.rest('water-administrations', 'create', data=wa_data)
            log.info(
                f"Water administered registered in Alyx database: {ses['subject']},"
                f"{settings_dict['TOTAL_WATER_DELIVERED'] / 1000}mL"
            )
