===============
Developer Guide
===============

Versioning Scheme
=================

IBLRIG v8 uses `Semantic Versioning 2.0.0 <https://semver.org/spec/v2.0.0.html>`_.
Its version string (currently "|version|") is a combination of three fields, separated by dots:

.. centered:: ``MAJOR`` . ``MINOR`` . ``PATCH``

* The ``MAJOR`` field is only incremented for breaking changes, i.e., changes that are not backward compatible with previous changes.
  Releases of IBLRIG v8, for instance, are generally incompatible with IBLRIG v7.
* The ``MINOR`` field will be incremented upon adding new, backwards compatible features.
* The ``PATCH`` field will be incremented with each new, backwards compatible bugfix release that does not implement a new feature.

On the developer side, these 3 fields are manually controlled by, both

   1. adjusting the variable ``__version__`` in ``iblrig/__init__.py``, and
   2. adding the corresponding version string to a commit as a `git tag <https://git-scm.com/book/en/v2/Git-Basics-Tagging>`_,
      for instance:

      .. code-block:: console

         git tag 8.8.4
         git push origin --tags

The version string displayed by IBLRIG *may* include additional fields, such as in "|version|.post3+dirty".
Here,

* ``post3`` indicates the third unversioned commit after the latest versioned release, and
* ``dirty`` indicates the presence of uncommited changes in your local repository of IBLRIG.

Both of these fields are inferred by means of git describe and do not require manual interaction from the developer.


Running Tests Locally
=====================

.. code-block:: console

   flake8
   python -m unittest discover ./iblrig/test


Building the documentation
==========================

.. code-block:: console

   # make sure pre-requisites are installed
   pip install --upgrade -e .[DEV]
   # create the static directory
   rm -rf ./docs/build
   mkdir -p ./docs/build/html/_static
   # unit tests generate task diagrams
   python -m unittest discover ./iblrig/test
   # generate class diagrams
   pyreverse -o png -m y --ignore iblrig.test -A --output-directory ./docs/build/html/_static ./iblrig_tasks
   # build and serve the docs locally
   sphinx-autobuild ./docs/source ./docs/build/html/



Guide to Creating Your Own Task
===============================

What Happens When Running an IBL Task?
--------------------------------------

1. The task constructor is invoked, executing the following steps:

   -  Reading of settings: hardware and IBLRIG configurations.
   -  Reading of task parameters.
   -  Instantiation of hardware mixins.

2. The task initiates the ``run()`` method. Prior to execution, this
   method:

   -  Launches the hardware modules.
   -  Establishes a session folder.
   -  Saves the parameters to disk.

3. The experiment unfolds: the ``run()`` method triggers the ``_run()``
   method within the child class:

   -  Typically, this involves a loop that generates a Bpod state
      machine for each trial and runs it.

4. Upon SIGINT or when the maximum trial count is reached, the
   experiment concludes. The end of the ``run()`` method includes:

   -  Saving the final parameter file.
   -  Recording administered water and session performance on Alyx.
   -  Halting the mixins.
   -  Initiating local server transfer.

Writing Your Own Task
---------------------

iblrig.base_tasks.BaseTask
~~~~~~~~~~~~~~~~~~~~~~~~~~

This serves as the fundamental class for all tasks. It supplies abstract
methods and functions to establish the folder structure and perform Alyx
database registration.

1. When creating a subclass of BaseTask, you must override the following
   methods:

   -  ``_run()``: Main method of the task, wrapped by the ``run()``
      method that incorporates folder creation and Alyx interaction pre-
      and post-task.
   -  ``start_hardware()``: Method to activate hardware modules and
      establish connections.

2. Document your protocol name using the ``protocol_name`` property.

Hardware Modules
^^^^^^^^^^^^^^^^

Within ``iblrig.base_tasks``, hardware mixins are dedicated to specific
modules. These mixin classes deliver hardware-specific functionality. To
use those mixins, compose them with the ``BaseClass`` above.

Mixins for hardware modules decouple hardware-specific code from task
code: - The ``init_mixin_*()`` methods are called at instantiation, so
they need to work regardless of whether the hardware is connected or
not. - The ``start_mixin_*()`` methods are called at the beginning of
the ``run()`` method, ensuring that the hardware is properly connected.
- The ``stop_mixin_*()`` methods are called at the end of the ``run()``
method, ensuring that the hardware is properly disconnected.

To test only the hardware, you can instantiate the task and call the
``start_hardware()`` and ``stop_hardware()`` methods.

iblrig.base_choice_world.ChoiceWorld
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is a subclass of ``BaseTask`` that implements the IBL
decision-making task family. When subclassing ``ChoiceWorld``, you must
override the following methods: - ``next_trial()``
