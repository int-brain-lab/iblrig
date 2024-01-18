import datetime
import time

import numpy as np
import pandas as pd

from iblrig.raw_data_loaders import load_task_jsonable
from iblrig.test.base import PATH_FIXTURES, TASK_KWARGS, BaseTestCases, IntegrationFullRuns
from iblrig_tasks._iblrig_tasks_biasedChoiceWorld.task import Session as BiasedChoiceWorldSession
from iblrig_tasks._iblrig_tasks_ephysChoiceWorld.task import Session as EphysChoiceWorldSession
from iblrig_tasks._iblrig_tasks_ImagingChoiceWorld.task import Session as ImagingChoiceWorldSession
from iblrig_tasks._iblrig_tasks_neuroModulatorChoiceWorld.task import Session as NeuroModulatorChoiceWorldSession


class TestInstantiationBiased(BaseTestCases.CommonTestInstantiateTask):
    def setUp(self) -> None:
        self.task = BiasedChoiceWorldSession(**TASK_KWARGS)
        np.random.seed(12345)

    def test_task(self, reward_set=np.array([0, 1.5])):
        task = self.task
        task.create_session()
        trial_fixtures = get_fixtures()
        nt = 500
        t = np.zeros(nt)
        for i in np.arange(nt):
            t[i] = time.time()
            task.next_trial()
            # pc = task.psychometric_curve()
            trial_type = np.random.choice(['correct', 'error', 'no_go'], p=[0.9, 0.05, 0.05])
            task.trial_completed(trial_fixtures[trial_type])
            if trial_type == 'correct':
                self.assertTrue(task.trials_table['trial_correct'][task.trial_num])
            else:
                self.assertFalse(task.trials_table['trial_correct'][task.trial_num])
            if i == 245:
                task.show_trial_log()
            assert not np.isnan(task.reward_time)
        # test the trial table results
        task.trials_table = task.trials_table[: task.trial_num + 1]
        np.testing.assert_array_equal(task.trials_table['trial_num'].values, np.arange(task.trial_num + 1))
        # makes sure the water reward counts check out
        assert task.trials_table['reward_amount'].sum() == task.session_info.TOTAL_WATER_DELIVERED
        assert np.sum(task.trials_table['reward_amount'] == 0) == task.trial_num + 1 - task.session_info.NTRIALS_CORRECT
        assert np.all(~np.isnan(task.trials_table['reward_valve_time']))
        # Test the blocks task logic
        df_blocks = task.trials_table.groupby('block_num').agg(
            count=pd.NamedAgg(column='stim_angle', aggfunc='count'),
            n_stim_probability_left=pd.NamedAgg(column='stim_probability_left', aggfunc='nunique'),
            stim_probability_left=pd.NamedAgg(column='stim_probability_left', aggfunc='first'),
            position=pd.NamedAgg(column='position', aggfunc=lambda x: 1 - (np.mean(np.sign(x)) + 1) / 2),
            first_trial=pd.NamedAgg(column='block_trial_num', aggfunc='first'),
        )
        # test that the first block is 90 trials
        assert df_blocks['count'].values[0] == 90
        # make all first block trials were reset to 0
        assert np.all(df_blocks['first_trial'] == 0)
        # test that the first block has 50/50 probability
        assert df_blocks['stim_probability_left'].values[0] == 0.5
        # make sure that all subsequent blocks alternate between 0.2 and 0.8 left probability
        assert np.all(np.isclose(np.abs(np.diff(df_blocks['stim_probability_left'].values[1:])), 0.6))
        # assert the the trial outcomes are within 0.3 of the generating probability
        np.testing.assert_array_less(np.abs(df_blocks['position'] - df_blocks['stim_probability_left']), 0.4)
        np.testing.assert_array_equal(np.unique(task.trials_table['reward_amount']), reward_set)

    def check_quiescent_period(self):
        """
        Check that the quiescence period is between 0.4 and 0.8
        Overload this method for a change in quiescent period
        """
        self.assertTrue(np.all(self.task.trials_table['quiescent_period'] > 0.4))
        self.assertTrue(np.all(self.task.trials_table['quiescent_period'] < 0.8))


class TestImagingChoiceWorld(TestInstantiationBiased):
    def setUp(self) -> None:
        self.task = ImagingChoiceWorldSession(**TASK_KWARGS)


class TestInstantiationEphys(TestInstantiationBiased):
    def setUp(self) -> None:
        self.task = EphysChoiceWorldSession(**TASK_KWARGS)


class TestNeuroModulatorBiasedChoiceWorld(TestInstantiationBiased):
    def setUp(self) -> None:
        self.task = NeuroModulatorChoiceWorldSession(**TASK_KWARGS)

    def test_task(self):
        super().test_task(reward_set=np.array([0, 1.0, 1.5, 3.0]))
        # we expect 10% of null feedback trials
        assert np.abs(0.05 - np.mean(self.task.trials_table['omit_feedback'])) < 0.05


class TestIntegrationFullRun(IntegrationFullRuns):
    def setUp(self) -> None:
        super().setUp()
        self.task = BiasedChoiceWorldSession(one=self.one, **self.kwargs)

    def test_task_biased(self):
        """
        Run mocked task for 3 trials
        Registers sessions on Alyx at startup, and post-hoc registers number of trials
        :return:
        """
        task = self.task
        task.mock(
            file_jsonable_fixture=PATH_FIXTURES.joinpath('task_data_short.jsonable'),
        )
        task.task_params.NTRIALS = 3
        task.session_info['SUBJECT_WEIGHT'] = 24.2  # manually add a weighing
        # manually add water delivered since we test with few trials, there is a chance that this
        # value ends up being zero, in which case the water administration is not registered and test fails
        # if one trial gets rewarded, then water delivered will be more than the amount below
        init_water = 12.2
        task.session_info['TOTAL_WATER_DELIVERED'] = init_water
        task.run()
        file_settings = task.paths.SESSION_RAW_DATA_FOLDER.joinpath('_iblrig_taskSettings.raw.json')
        settings = self.read_and_assert_json_settings(file_settings)
        # makes sure the session end time is labeled
        dt = datetime.datetime.now() - datetime.datetime.fromisoformat(settings['SESSION_END_TIME'])
        self.assertLess(dt.seconds, 600)  # leaves some time for debugging
        trials_table, bpod_data = load_task_jsonable(task.paths.SESSION_RAW_DATA_FOLDER.joinpath('_iblrig_taskData.raw.jsonable'))
        assert trials_table.shape[0] == task.task_params.NTRIALS
        assert len(bpod_data) == task.task_params.NTRIALS
        # test that Alyx registration went well, we should find the session
        ses = self.one.alyx.rest(
            'sessions',
            'list',
            subject=self.kwargs['subject'],
            date=task.session_info['SESSION_START_TIME'][:10],
            number=task.session_info['SESSION_NUMBER'],
        )
        full_session = self.one.alyx.rest('sessions', 'read', id=ses[0]['id'])
        self.assertEqual(set(full_session['projects']), set(self.kwargs['projects']))
        self.assertEqual(set(full_session['procedures']), set(self.kwargs['procedures']))
        # and the water administered
        assert full_session['wateradmin_session_related'][0]['water_administered'] == init_water / 1000
        # and the related weighing
        wei = self.one.alyx.rest(
            'weighings', 'list', nickname=self.kwargs['subject'], date=task.session_info['SESSION_START_TIME'][:10]
        )
        assert wei[0]['weight'] == task.session_info['SUBJECT_WEIGHT']


def get_fixtures():
    correct_trial = {
        'Bpod start timestamp': 0.0,
        'Trial start timestamp': 15.570999999999998,
        'Trial end timestamp': 50.578703,
        'States timestamps': {
            'trial_start': [[15.570999999999998, 15.571099999999998]],
            'reset_rotary_encoder': [
                [15.571099999999998, 15.571199999999997],
                [15.671399999999998, 15.671499999999998],
                [15.765699999999999, 15.765799999999999],
                [15.793999999999997, 15.794099999999997],
                [15.8112, 15.8113],
                [15.825199999999999, 15.825299999999999],
                [15.838099999999997, 15.838199999999997],
                [15.851599999999998, 15.851699999999997],
                [15.871199999999998, 15.871299999999998],
                [15.946299999999997, 15.946399999999997],
                [16.0142, 16.0143],
                [16.036699999999996, 16.0368],
                [16.055, 16.0551],
                [16.0708, 16.070899999999998],
                [16.0858, 16.0859],
                [16.099999999999998, 16.100099999999998],
                [16.1147, 16.1148],
                [16.1316, 16.1317],
                [16.150999999999996, 16.1511],
                [16.171599999999998, 16.171699999999998],
                [16.192899999999998, 16.192999999999998],
                [16.214899999999997, 16.214999999999996],
                [16.238599999999998, 16.238699999999998],
                [16.263399999999997, 16.263499999999997],
                [16.2901, 16.2902],
                [16.3163, 16.316399999999998],
                [16.3401, 16.3402],
                [16.362699999999997, 16.362799999999996],
                [16.385499999999997, 16.385599999999997],
                [16.4121, 16.4122],
                [16.4976, 16.4977],
                [16.542299999999997, 16.542399999999997],
                [16.615899999999996, 16.616],
                [16.9041, 16.9042],
            ],
            'quiescent_period': [
                [15.571199999999997, 15.671399999999998],
                [15.671499999999998, 15.765699999999999],
                [15.765799999999999, 15.793999999999997],
                [15.794099999999997, 15.8112],
                [15.8113, 15.825199999999999],
                [15.825299999999999, 15.838099999999997],
                [15.838199999999997, 15.851599999999998],
                [15.851699999999997, 15.871199999999998],
                [15.871299999999998, 15.946299999999997],
                [15.946399999999997, 16.0142],
                [16.0143, 16.036699999999996],
                [16.0368, 16.055],
                [16.0551, 16.0708],
                [16.070899999999998, 16.0858],
                [16.0859, 16.099999999999998],
                [16.100099999999998, 16.1147],
                [16.1148, 16.1316],
                [16.1317, 16.150999999999996],
                [16.1511, 16.171599999999998],
                [16.171699999999998, 16.192899999999998],
                [16.192999999999998, 16.214899999999997],
                [16.214999999999996, 16.238599999999998],
                [16.238699999999998, 16.263399999999997],
                [16.263499999999997, 16.2901],
                [16.2902, 16.3163],
                [16.316399999999998, 16.3401],
                [16.3402, 16.362699999999997],
                [16.362799999999996, 16.385499999999997],
                [16.385599999999997, 16.4121],
                [16.4122, 16.4976],
                [16.4977, 16.542299999999997],
                [16.542399999999997, 16.615899999999996],
                [16.616, 16.9041],
                [16.9042, 17.3646],
            ],
            'stim_on': [[17.3646, 17.464599999999997]],
            'reset2_rotary_encoder': [[17.464599999999997, 17.464699999999997]],
            'closed_loop': [[17.464699999999997, 49.5787]],
            'reward': [[49.5787, 49.7357]],
            'correct': [[49.7357, 50.5787]],
            'no_go': [[np.nan, np.nan]],
            'error': [[np.nan, np.nan]],
        },
        'Events timestamps': {
            'Tup': [
                15.571099999999998,
                15.571199999999997,
                15.671499999999998,
                15.765799999999999,
                15.794099999999997,
                15.8113,
                15.825299999999999,
                15.838199999999997,
                15.851699999999997,
                15.871299999999998,
                15.946399999999997,
                16.0143,
                16.0368,
                16.0551,
                16.070899999999998,
                16.0859,
                16.100099999999998,
                16.1148,
                16.1317,
                16.1511,
                16.171699999999998,
                16.192999999999998,
                16.214999999999996,
                16.238699999999998,
                16.263499999999997,
                16.2902,
                16.316399999999998,
                16.3402,
                16.362799999999996,
                16.385599999999997,
                16.4122,
                16.4977,
                16.542399999999997,
                16.616,
                16.9042,
                17.3646,
                17.464599999999997,
                17.464699999999997,
                49.7357,
                50.5787,
            ],
            'BNC1Low': [
                15.637299999999996,
                17.5215,
                18.539299999999997,
                19.436799999999998,
                19.5706,
                20.554499999999997,
                21.504299999999997,
                22.6711,
                25.2047,
                26.254399999999997,
                26.7207,
                29.3714,
                29.8217,
                30.9204,
                30.986399999999996,
                31.387700000000002,
                31.770000000000003,
                31.9047,
                32.5047,
                32.6044,
                33.8876,
                33.9882,
                34.1033,
                34.1703,
                34.5395,
                35.62,
                36.7697,
                37.236,
                37.2703,
                37.305,
                37.3701,
                37.4382,
                37.7558,
                38.1703,
                38.3527,
                38.4197,
                38.5538,
                38.620200000000004,
                39.936699999999995,
                40.6881,
                41.7549,
                42.5024,
                42.585,
                43.035999999999994,
                44.1039,
                49.2046,
                49.4698,
                49.5368,
                49.6195,
            ],
            'RotaryEncoder1_4': [
                15.671399999999998,
                15.765699999999999,
                15.793999999999997,
                15.8112,
                15.825199999999999,
                15.838099999999997,
                15.851599999999998,
                15.871199999999998,
                15.946299999999997,
                16.0142,
                16.036699999999996,
                16.055,
                16.0708,
                16.0858,
                16.099999999999998,
                16.1147,
                16.1316,
                16.150999999999996,
                16.171599999999998,
                16.192899999999998,
                16.214899999999997,
                16.238599999999998,
                16.263399999999997,
                16.2901,
                16.3163,
                16.3401,
                16.362699999999997,
                16.385499999999997,
                16.4121,
                16.4976,
                16.542299999999997,
                16.615899999999996,
                16.9041,
                18.5982,
            ],
            'BNC1High': [
                17.406499999999998,
                18.4564,
                18.656399999999998,
                19.5231,
                19.639799999999997,
                21.323,
                21.573,
                24.0396,
                25.3395,
                26.356099999999998,
                28.3894,
                29.422599999999996,
                30.8226,
                30.9559,
                31.022599999999997,
                31.7226,
                31.822499999999998,
                31.939100000000003,
                32.5556,
                33.422599999999996,
                33.939,
                34.0391,
                34.1224,
                34.2891,
                35.2105,
                36.522299999999994,
                37.1889,
                37.2387,
                37.2724,
                37.3222,
                37.4056,
                37.4723,
                37.8723,
                38.238899999999994,
                38.3722,
                38.4723,
                38.5723,
                39.4222,
                40.0555,
                40.9388,
                42.3555,
                42.522,
                42.7554,
                43.672000000000004,
                46.5053,
                49.321799999999996,
                49.4718,
                49.571799999999996,
            ],
            'RotaryEncoder1_3': [33.9907],
            'RotaryEncoder1_2': [49.5787],
        },
    }  # noqa
    error_trial = {
        'Bpod start timestamp': 0.0,
        'Trial start timestamp': 0.0,
        'Trial end timestamp': 15.485902,
        'States timestamps': {
            'trial_start': [[0.0, 0.00010000000000021103]],
            'reset_rotary_encoder': [
                [0.00010000000000021103, 0.00019999999999997797],
                [0.4855999999999998, 0.4857],
                [0.5165000000000002, 0.5166],
                [0.5331999999999999, 0.5333000000000001],
                [0.5461999999999998, 0.5463],
                [0.5590999999999999, 0.5592000000000001],
                [0.5741, 0.5742000000000003],
                [0.5952999999999999, 0.5954000000000002],
            ],
            'quiescent_period': [
                [0.00019999999999997797, 0.4855999999999998],
                [0.4857, 0.5165000000000002],
                [0.5166, 0.5331999999999999],
                [0.5333000000000001, 0.5461999999999998],
                [0.5463, 0.5590999999999999],
                [0.5592000000000001, 0.5741],
                [0.5742000000000003, 0.5952999999999999],
                [0.5954000000000002, 1.1006],
            ],
            'stim_on': [[1.1006, 1.2006000000000006]],
            'reset2_rotary_encoder': [[1.2006000000000006, 1.2007000000000003]],
            'closed_loop': [[1.2007000000000003, 13.4859]],
            'error': [[13.4859, 15.4859]],
            'no_go': [[np.nan, np.nan]],
            'reward': [[np.nan, np.nan]],
            'correct': [[np.nan, np.nan]],
        },
        'Events timestamps': {
            'Tup': [
                0.00010000000000021103,
                0.00019999999999997797,
                0.4857,
                0.5166,
                0.5333000000000001,
                0.5463,
                0.5592000000000001,
                0.5742000000000003,
                0.5954000000000002,
                1.1006,
                1.2006000000000006,
                1.2007000000000003,
                15.4859,
            ],
            'BNC1High': [
                0.07390000000000008,
                1.3236999999999997,
                1.7572,
                2.5072,
                5.1071,
                10.1735,
                10.273399999999999,
                10.3065,
                10.8901,
                11.023399999999999,
                11.64,
                11.739999999999998,
                11.9068,
                12.04,
                12.3067,
                12.6066,
                12.773399999999999,
                12.940000000000001,
                13.3734,
                13.423300000000001,
                13.523399999999999,
            ],
            'RotaryEncoder1_4': [
                0.4855999999999998,
                0.5165000000000002,
                0.5331999999999999,
                0.5461999999999998,
                0.5590999999999999,
                0.5741,
                0.5952999999999999,
                1.7535999999999996,
            ],
            'BNC1Low': [
                1.1719,
                1.5057,
                1.8071000000000002,
                3.6715,
                9.321200000000001,
                10.2713,
                10.304300000000001,
                10.822600000000001,
                10.938099999999999,
                11.0551,
                11.7211,
                11.822099999999999,
                12.023399999999999,
                12.188400000000001,
                12.3885,
                12.6557,
                12.8888,
                13.1539,
                13.405999999999999,
                13.4541,
            ],
            'RotaryEncoder1_3': [1.1886, 11.780000000000001],
            'RotaryEncoder1_1': [13.4859],
        },
    }  # noqa
    no_go_trial = {
        'Bpod start timestamp': 0.0,
        'Trial start timestamp': 2950.106299,
        'Trial end timestamp': 3012.791701,
        'States timestamps': {
            'trial_start': [[2950.106299, 2950.1063990000002]],
            'reset_rotary_encoder': [
                [2950.1063990000002, 2950.106499],
                [2950.120499, 2950.120599],
                [2950.139099, 2950.139199],
                [2950.161899, 2950.161999],
                [2950.194099, 2950.194199],
            ],
            'quiescent_period': [
                [2950.106499, 2950.120499],
                [2950.120599, 2950.139099],
                [2950.139199, 2950.161899],
                [2950.161999, 2950.194099],
                [2950.194199, 2950.691599],
            ],
            'stim_on': [[2950.691599, 2950.791599]],
            'reset2_rotary_encoder': [[2950.791599, 2950.791699]],
            'closed_loop': [[2950.791699, 3010.791699]],
            'no_go': [[3010.791699, 3012.791699]],
            'error': [[np.nan, np.nan]],
            'reward': [[np.nan, np.nan]],
            'correct': [[np.nan, np.nan]],
        },
        'Events timestamps': {
            'Tup': [
                2950.1063990000002,
                2950.106499,
                2950.120599,
                2950.139199,
                2950.161999,
                2950.194199,
                2950.691599,
                2950.791599,
                2950.791699,
                3010.791699,
                3012.791699,
            ],
            'RotaryEncoder1_3': [2950.120499, 2950.139099, 2950.161899, 2950.194099, 2981.703499],
            'BNC1Low': [
                2950.181299,
                2950.8635990000002,
                2960.946299,
                2961.162399,
                2961.262399,
                2976.078899,
                2981.678699,
                2981.761199,
                2981.828799,
                2981.862799,
                2981.928699,
                2982.0121990000002,
                2995.844699,
                2996.912299,
                2997.028199,
                2997.161899,
                2997.311999,
                2997.978999,
                3005.278699,
                3005.427699,
                3005.4786990000002,
                3005.610799,
                3005.927599,
                3011.129099,
                3011.178199,
                3011.245099,
            ],
            'BNC1High': [
                2950.750499,
                2960.766799,
                2960.983499,
                2961.183399,
                2975.849599,
                2981.549399,
                2981.715999,
                2981.799199,
                2981.832599,
                2981.899299,
                2981.965999,
                2982.099399,
                2995.865499,
                2996.9152990000002,
                2997.082199,
                2997.215499,
                2997.415399,
                3005.2484990000003,
                3005.365199,
                3005.448499,
                3005.515099,
                3005.881899,
                3006.065199,
                3011.148299,
                3011.181399,
            ],
            'RotaryEncoder1_4': [2961.126499],
            'RotaryEncoder1_1': [3011.1679990000002],
        },
    }  # noqa
    return dict(correct=correct_trial, error=error_trial, no_go=no_go_trial)
