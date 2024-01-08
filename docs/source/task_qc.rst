Quality check the task post-usage
=================================

Once a session is acquired, you can verify whether the acquired sequence of events matches the expected logic of
the task. For example, is it expected to acquire one and only one goCue per trial.

Metrics definitions
-------------------
All the metrics computed as part of the Task logic integrity QC (Task QC) are implemented in
`ibllib<https://github.com/int-brain-lab/ibllib/blob/master/ibllib/qc/task_metrics.py>`__.
They are computed using either the Bpod or FGPA/PXI data, depending on the rig used.

.. tip::

     The Task QC metrics definitions can be found in this
    `documentation page<https://int-brain-lab.github.io/iblenv/_autosummary/ibllib.qc.task_metrics.html>`__


Some are essential, i.e. if they fail you should immediately take action and verify your rig,
and some are not as critical.

Essential taskQCs:
* check_audio_pre_trial
* check_correct_trial_event_sequence
* check_error_trial_event_sequence
* check_n_trial_events
* check_response_feedback_delays
* check_reward_volume_set
* check_reward_volumes
* check_stimOn_goCue_delays
* check_stimulus_move_before_goCue
* check_wheel_move_before_feedback
* check_wheel_freeze_during_quiescence

Non essential taskQCs:
* check_stimOff_itiIn_delays
* check_positive_feedback_stimOff_delays
* check_negative_feedback_stimOff_delays
* check_wheel_move_during_closed_loop
* check_response_stimFreeze_delays
* check_detected_wheel_moves
* check_trial_length
* check_goCue_delays
* check_errorCue_delays
* check_stimOn_delays
* check_stimOff_delays
* check_iti_delays
* check_stimFreeze_delays
* check_wheel_integrity

.. tip::

     The value returned by each metric is the proportion of trial that fail to pass the given test.
     For example, if the value returned by ``check_errorCue_delays`` is 0.92, it means 8% of the trials failed this test.

Quantifying the task QC outcome at the session level
----------------------------------------------------

The criteria for whether a session passes the Task QC is:
* ``NOT_SET``: default value  (= not run yet)
* ``FAIL``: if at least one metric is < 95%
* ``WARNING``: if all metrics are >=95% , and at least one metric is <99 %
* ``PASS``: if all metrics are >= 99%

This aggregation is done on all metrics, regardless if they are essential or not.

The criteria is defined at
`this code line<https://github.com/int-brain-lab/ibllib/blob/master/ibllib/qc/task_metrics.py#L63 >`__

How to check the task QC outcome
--------------------------------

Once the session is registered on Alyx
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
1. **Check on the Alyx webpage**

   From the `session overview page on Alyx<https://alyx.internationalbrainlab.org/ibl_reports/gallery/sessions>`__,
   find your session click on ``See more session info ``.
   The session QC is displayed in one of the right panels.

   To get more information regarding which test pass or fail (contributing to this overall session QC),
   you can click on the ``QC`` menu on the left. Bar-diagrams will appear, with essentials QCs on the
   left, colored in green if passing.

   .. tip::
        You can hover over the bars with your mouse to easily know the name of the corresponding metric.
        This is useful if the value of the metric is ``0``.

.. warning::
    If an :ref:`essential metric<Metrics definitions>` fails, run the Task QC Viewer to investigate why.

2. **Run the taskQC Viewer to investigate**

    The application `Task QC Viewer<https://github.com/int-brain-lab/iblapps/blob/develop/task_qc_viewer/README.md >`__
    enables to visualise the data streams of problematic trials.

    .. tip::
        Make sure you are up-to-date on the following branches:
        * develop on ibllib
        * master on iblapps


.. exercise:: Run the task QC metrics and viewer

   Select the ``eid`` for your session to inspect, and run the following Python code:

   .. code-block:: python

      """
      Plot the task QC for a session.
      """
      ### RUN QC FROM ANYWHERE AFTER THE SESSION HAD BEEN REGISTERED ###


      from one.api import ONE
      from ibllib.io.session_params import read_params
      import ibllib.pipes.dynamic_pipeline as dyn
      from ibllib.io.extractors.base import get_pipeline, get_session_extractor_type
      from ibllib.pipes.dynamic_pipeline import get_trials_tasks
      from task_qc_viewer.task_qc import show_session_task_qc


      EID = 'baecbddc-2b86-4eaf-a6f2-b30923225609'
      one = ONE()

      # Get first none passive task run
      task = next(t for t in get_trials_tasks(one.eid2path(EID), one) if 'passive' not in t.name.lower())
      task.location = 'remote'
      task.setUp()  # Download the task data
      qc = task._run_qc(update=False)
      show_session_task_qc(qc_or_session=qc)
