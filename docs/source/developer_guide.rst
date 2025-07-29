Developer Guide
===============


Versioning Scheme
-----------------

IBLRIG v8 uses `Semantic Versioning <https://semver.org/spec/v2.0.0.html>`_.
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

Both of these fields are automatically inferred (by means of ``git describe``) and do not require manual interaction from the
developer.


Package Management and Development Workflows with PDM
-----------------------------------------------------

We use `PDM <https://pdm-project.org/en/latest/>`_ to manage dependencies of IBLRIG.
PDM can also be used to run various commands with relevance to the development process without having to activate a virtual
environment first.
Please refer to `PDM's documentation <https://pdm-project.org/en/latest/#installation>`_ for help with installing PDM.


Installing Developer Dependencies
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To install additional dependencies needed for working on IBLRIG's code-base, run:

.. code-block:: console

   pdm sync -d


Running Unit Tests
^^^^^^^^^^^^^^^^^^

To run unit tests locally, run:

.. code-block:: console

   pdm run pytest

This will also generate a HTML based coverage report which can be found in the ``htmlcov`` directory.


Linting & Formatting
^^^^^^^^^^^^^^^^^^^^

We use `Ruff <https://docs.astral.sh/ruff>`_ for linting and formatting our code-base in close accordance with `the Black code
style <https://black.readthedocs.io/en/stable/the_black_code_style/current_style.html>`_.

To lint your code, run:

.. code-block:: console

   pdm run ruff check

Appending the flag ``--fix`` to the above command will automatically fix issues that are deemed safe to handle.

To reformat your code according to the `Black code style <https://black.readthedocs.io/en/stable/the_black_code_style/current_style.html>`_ run:

.. code-block:: console

   pdm run ruff format

Appending the flag ``--check`` to the above command will check your code for formatting issues without applying any changes.
Refer to `Ruff Formater's documentation <https://docs.astral.sh/ruff/formatter/>`_ for further details.


pre-commit
----------

IBLRIG v8 supports pre-commit hooks.
Install pre-commit according to the `official guide <https://pre-commit.com/#install>`_ to enable automated code-checks on commits.


Release Checklist
-----------------

1) update CHANGELOG.md including changes from the last tag
2) Pull request to ``iblrigv8dev``
3) Check CI and eventually wet lab test
4) Pull request to ``iblrigv8``
5) Merge PR
6) git tag the release in accordance to the version number below (after merge!)


Building the documentation
--------------------------

To build the documentation, run:

.. code-block:: console

   pdm run sphinx-autobuild ./docs/source ./docs/build

You can also export the documentation to a PDF file:

.. code-block:: console

   pdm run make -C docs/ simplepdf

Find the exported PDF file in ``docs/build/simplepdf``.


Contribute to the documentation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To write the documentation:

* Write the documentation in the ``iblrig/docs/source`` folder
* If you are writing in a new file, add it to the ``index.rst`` so it appears in the table of content
* Push all your changes to the ``iblrigv8dev`` branch; if this branch does not exist, create it first

To release the documentation onto the `website <https://int-brain-lab.github.io/iblrig>`_:

* Wait for the next release, or
* Manually trigger the GitHub action by clicking "Run Workflow" (select ``iblrigv8dev``) `here <https://github.com/int-brain-lab/iblrig/actions/workflows/documentation.yaml>`_
