from pathlib import Path

import yaml

import iblrig.misc
from iblrig.base_choice_world import TrainingChoiceWorldSession

# read defaults from task_parameters.yaml
with open(Path(__file__).parent.joinpath('task_parameters.yaml')) as f:
    DEFAULTS = yaml.safe_load(f)


class Session(TrainingChoiceWorldSession):
    protocol_name = '_iblrig_tasks_trainingPhaseChoiceWorld'
    extractor_tasks = ['TrialRegisterRaw', 'ChoiceWorldTrials', 'TrainingStatus']

    def __init__(self, *args, training_level=DEFAULTS['TRAINING_PHASE'], debias=DEFAULTS['DEBIAS'], **kwargs):
        super(Session, self).__init__(*args, training_phase=training_level, **kwargs)
        self.task_params['TRAINING_PHASE'] = training_level
        self.task_params['DEBIAS'] = debias

    def check_training_phase(self):
        pass

    @staticmethod
    def extra_parser():
        """:return: argparse.parser()"""
        parser = super(Session, Session).extra_parser()
        parser.add_argument(
            '--training_level',
            option_strings=['--training_level'],
            dest='training_level',
            default=DEFAULTS['TRAINING_PHASE'],
            type=int,
            help='defines the set of contrasts presented to the subject',
        )
        parser.add_argument(
            '--debias',
            option_strings=['--debias'],
            dest='debias',
            default=DEFAULTS['DEBIAS'],
            type=bool,
            help='uses the debiasing protocol (only applies to levels 0-4)',
        )
        return parser


if __name__ == '__main__':  # pragma: no cover
    kwargs = iblrig.misc.get_task_arguments(parents=[Session.extra_parser()])
    sess = Session(**kwargs)
    sess.run()
