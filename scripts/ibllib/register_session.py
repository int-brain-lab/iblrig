import logging
import sys
import traceback

from ibllib.oneibl.registration import IBLRegistrationClient

log = logging.getLogger('iblrig')


if __name__ == '__main__':
    IBLRIG_DATA = sys.argv[1]
    try:
        log.info('Trying to register session in Alyx...')
        IBLRegistrationClient(one=None).create_sessions(IBLRIG_DATA, dry=False)
        log.info('Done')
    except Exception:
        log.error(traceback.format_exc())
        log.warning('Failed to register session on Alyx, will try again from local server after transfer')
