# from iblrig.base_choice_world import ChoiceWorldSession

from iblrig.base_choice_world import BiasedChoiceWorldSession

cw = BiasedChoiceWorldSession(interactive=False, subject='harp_validator_subject')
cw.start_mixin_bpod()
cw.start_mixin_sound()
