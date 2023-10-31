==============================
Guide to develop a custom task
==============================

The basics
==========

During the lifetime of the IBL project, we realized that multiple task variants combine with multiple hardware configurations and acquisition modalities, leading to a combinatorial explosion of possible tasks and related hardware.

This left us with the only option of developing a flexible task framework through hierarchical inheritance.

All tasks inherit from the ``iblrig.base_tasks.BaseSession`` class, which provides the following functionalities:
    -   read hardware parameters and rig parameters
    -   optionally interfaces with the `Alyx experimental database <https://github.com/cortex-lab/alyx>`_
    -   creates the folder structure for the session
    -   writes the task and rig parameters, log, and :doc:`acquisition description files <../description_file>`

Additionally the ``iblrig.base_tasks`` module provides "hardware mixins". Those are classes that provide hardware-specific functionalities, such as connecting to a Bpod or a rotary encoder. They are composed with the ``BaseSession`` class to create a task.

.. warning::

    This sounds complicated ? It is !
    Forecasting all possible tasks and hardware add-ons and modification is fool's errand, however we can go through specific examples of task implementations.



Examples
========

.. admonition:: Where to write your task
    :class: seealso

    After the :doc:`installation of iblrig <../installation>` the `project extraction <https://github.com/int-brain-lab/project_extraction>`_ repository is located at the root of the C: drive.
    New tasks should be added to the ``C:\project_extraction\iblrig_custom_tasks`` folder to be made visible by the `iblrig` GUI.
    We use a convention that the task name starts with the author identifier, followed by an underscore, followed by the task name, such as `olivier_awesomeChoiceWorld`.


     olivier_awesomeChoiceWorld
        -   __init__.py
        -   task.py
        -   README.md
        -   task_parameters.yaml
        -   test_olivier_awesomeChoiceWorld.py


Example 1: variation on biased choice world
-------------------------------------------

We will create a a choice world task that modifies a the quiescence period duration random draw policy.
In the `task.py` file, the first step is to create a new task class that inherits from the ``BiasedChoiceWorldSession`` class.

Then we want to make sure that the task bears a distinctive protocol name, `_iblrig_tasks_imagingChoiceWorld`.
We also create the command line entry point for the task that will be used by the `iblrig` GUI.

Also, in this case we can leverage the IBL infrastructure to perform extraction of the trials using existing extractors `extractor_tasks = ['TrialRegisterRaw', 'ChoiceWorldTrials']`

   .. code-block:: python

        import iblrig.misc
        from iblrig.base_choice_world import BiasedChoiceWorldSession


        class Session(BiasedChoiceWorldSession):
            protocol_name = "_iblrig_tasks_imagingChoiceWorld"
            extractor_tasks = ['TrialRegisterRaw', 'ChoiceWorldTrials']

        if __name__ == "__main__":  # pragma: no cover
            kwargs = iblrig.misc.get_task_arguments(parents=[Session.extra_parser()])
            sess = Session(**kwargs)
            sess.run()


In this case the parent class `BiasedChoiceWorldSession` has a method that draws the quiescence period. We are going to overload this method to add our own policy. This means the parent method will be fully replaced by our implementation.
The class now looks like this:

   .. code-block:: python

        class Session(BiasedChoiceWorldSession):
            protocol_name = "_iblrig_tasks_imagingChoiceWorld"

            def draw_quiescent_period(self):
                """
                For this task we double the quiescence period texp draw and remove the absolute
                offset of 200ms. The resulting is a truncated exp distribution between 400ms and 1 sec
                """
                return iblrig.misc.texp(factor=0.35 * 2, min_=0.2 * 2, max_=0.5 * 2)

Et voilà, in a few lines, we re-used the whole biased choice world implementation to add a custom parameter. This is the most trivial and easy example.
The full code is available `here <https://github.com/int-brain-lab/iblrig/tree/iblrigv8/iblrig_tasks/_iblrig_tasks_ImagingChoiceWorld>`_.


Example 2: re-writing a state-machine for a biased choice world task
--------------------------------------------------------------------

In some instances changes in the task logic require to go deeper and re-write the sequence of task events. In bpod parlance, we are talking about rewritng the state-machine code.

Coming, for now here is an example of such a `task <https://github.com/int-brain-lab/iblrig/tree/iblrigv8/iblrig_tasks/_iblrig_tasks_neuroModulatorChoiceWorld>`_.