Quality check the task post-usage
=================================

Once a session is acquired, you can verify whether the trials data is extracted properly and that the sequence of events matches the expected logic of
the task.

Metrics definitions
-------------------
All the metrics computed as part of the Task logic integrity QC (Task QC) are implemented in
`ibllib <https://github.com/int-brain-lab/ibllib/blob/master/ibllib/qc/task_metrics.py>`__.
When run at a behavior rig, they are computed using the Bpod data, without alignment to another DAQ's clock.

.. tip::

     The Task QC metrics definitions can be found in this `documentation page <https://int-brain-lab.github.io/iblenv/_autosummary/ibllib.qc.task_metrics.html>`__.
     See `this page <write_your_own_task.html>`__ on how to write QC checks for a custom task protocol.


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
`this code line <https://github.com/int-brain-lab/ibllib/blob/master/ibllib/qc/task_metrics.py#L63>`__

How to check the task QC outcome
--------------------------------

Immediately after acquiring a session
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
At the behaviour PC, before the data have been copied, use the `task_qc` command with the session path:

.. code-block:: shell-session

    task_qc C:\iblrigv8_data\Subjects\KS022\2019-12-10\001 --local

More information can be found `here <https://github.com/int-brain-lab/ibllib/tree/master/ibllib/qc/task_qc_viewer#readme>`__, or by running `task_qc --help`.

Once the session is registered on Alyx
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
1. **Check on the Alyx webpage**

   From the `session overview page on Alyx <https://alyx.internationalbrainlab.org/ibl_reports/gallery/sessions>`__,
   find your session click on ``See more session info``.
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

    The application `Task QC Viewer <https://github.com/int-brain-lab/ibllib/tree/master/ibllib/qc/task_qc_viewer#readme>`__
    enables to visualise the data streams of problematic trials.

    .. tip::
        Unlike when run at the behaviour PC, after registration the QC is run on the final time-aligned data (if applicable).


    .. exercise:: Run the task QC metrics and viewer

       Select the ``eid`` for your session to inspect, and run the following within the iblrig env:

        .. code-block:: shell-session

            task_qc baecbddc-2b86-4eaf-a6f2-b30923225609
