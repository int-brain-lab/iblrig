import logging

from iblrig.base_choice_world import BiasedChoiceWorldSession

NTRIALS_INIT = 1000
log = logging.getLogger("iblrig")


class Session(BiasedChoiceWorldSession):
    def __init__(self, *args, **kwargs):
        super(Session, self).__init__(*args, **kwargs)
