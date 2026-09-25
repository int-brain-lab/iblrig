Describing an Experiment
========================

Experiment description file
---------------------------

All experiments are described by a file with the name
``_ibl_experiment.description.yaml``. This description file contains
details about the experiment such as, information about the devices used
to collect data, or the behavior tasks run during the experiment. The
content of this file is used to copy data from the acquisition computer
to the lab server and also determines the task pipeline that will be
used to extract the data on the lab servers. It’s accuracy in fully
describing the experiment is, therefore, very important!

Here is an example of a complete experiment description file for a
mesoscope experiment running two consecutive tasks,
``biasedChoiceWorld`` followed by ``passiveChoiceWorld``.

.. code:: yaml

   devices:
     mesoscope:
       mesoscope:
         collection: raw_imaging_data*
         sync_label: chrono
     cameras:
       belly:
         collection: raw_video_data
         sync_label: audio
         width: 640
         height: 512
         fps: 30
       left:
         collection: raw_video_data
         sync_label: audio
       right:
         collection: raw_video_data
         sync_label: audio
   procedures:
   - Imaging
   projects:
   - ibl_mesoscope_active
   sync:
     nidq:
       acquisition_software: timeline
       collection: raw_sync_data
       extension: npy
   tasks:
   - _biasedChoiceWorld:
       collection: raw_task_data_00
       sync_label: bpod
       extractors: [TrialRegisterRaw, ChoiceWorldTrialsTimeline, TrainingStatus]
   - passiveChoiceWorld:
       collection: raw_task_data_01
       sync_label: bpod
       extractors: [PassiveRegisterRaw, PassiveTaskTimeline]
   version: 1.0.0

Breaking down the components of an experiment description file
--------------------------------------------------------------

Devices
~~~~~~~

The devices section in the experiment description file lists the set of
devices from which data was collection in the experiment. Supported
devices are Cameras, Microphone, Mesoscope, Neuropixel, Photometry and
Widefield.

The convention for this section is to have the device name followed by a
list of sub-devices, e.g.

.. code:: yaml

   devices:
     cameras:
       belly:
         collection: raw_video_data
         sync_label: audio
         width: 640
         height: 512
         fps: 30
       left:
         collection: raw_video_data
         sync_label: audio
       right:
         collection: raw_video_data
         sync_label: audio

In the above example, ``cameras`` is the device and the sub-devices are
``belly``, ``left`` and ``right``.

If there are no sub-devices, the sub-device is given the same name as
the device, e.g.

.. code:: yaml

   devices:
     mesoscope:
       mesoscope:
         collection: raw_imaging_data*
         sync_label: chrono

Each sub-device must have at least the following two keys -
**collection** - the folder containing the data - **sync_label** - the
name of the common ttl pulses in the channel map used to sync the
timestamps

Additional keys can also be specified for specific extractors, e.g. for
the belly camera the camera metadata passed into the camera extractor
task is defined in this file.

Procedures
~~~~~~~~~~

The procedures section lists the set of procedures that apply to this
experiment. The list of possible procedures can be found
`here <https://alyx.internationalbrainlab.org/admin/actions/proceduretype/>`__.

As many procedure that apply to the experiment can be added e.g.

.. code:: yaml

   procedures:
   - Fiber photometry
   - Optical stimulation
   - Ephys recording with acute probe(s)

Projects
~~~~~~~~

The projects section lists the set of projects that apply to this
experiment. The list of possible projects can be found
`here <https://alyx.internationalbrainlab.org/admin/subjects/project/>`__.

As many projects that apply to the experiment can be added e.g.

::

   projects:
   - ibl_neuropixel_brainwide_01
   - carandiniharris_midbrain_ibl

Sync
~~~~

The sync section contains information about the device used to collect
the syncing data and the format of the data. Supported sync devices are
bpod, nidq, tdms, timeline. Only **one** sync device can be specified
per experiment description file and act as the main clock to which other
timeseries are synced.

An example of an experiment run with bpod as the main syncing device is,

.. code:: yaml

   sync:
     bpod:
       collection: raw_behavior_data
       extension: bin

Another example for spikeglx electrophysiology recordings with
Neuropixel 1B probes use the nidq as main synchronisation.

.. code:: yaml

   sync:
     nidq:
       collection: raw_ephys_data
       extension: bin
       acquisition_software: spikeglx

Each sync device must have at least the following two keys -
**collection** - the folder containing the data - **extension** - the
file extension of the sync data

Optional keys include, for example ``acquisition_software``, the
software used to acquire the sync pulses

Tasks
~~~~~

The tasks section contains a list of the behavioral protocols run during
the experiment. The name of the protocol must be given in the list e.g.

.. code:: yaml

   tasks:
   - _biasedChoiceWorld:
       collection: raw_task_data_00
       sync_label: bpod
       extractors: [TrialRegisterRaw, ChoiceWorldTrialsTimeline, TrainingStatus]
   - passiveChoiceWorld:
       collection: raw_task_data_01
       sync_label: bpod
       extractors: [PassiveRegisterRaw, PassiveTaskTimeline]

Each task must have at least the following two keys - **collection** -
the folder containing the data - **sync_label** - the name of the common
ttl pulses in the channel map used to sync the timestamps

The ``collection`` must be unique for each task. i.e. Data from two
tasks cannot be stored in the same folder.

If the Tasks used to extract the data are not the default tasks, the
extractors to use must be passed in as an additional key. The order of
the extractors defines their parent child relationship in the task
architecture.

Version
~~~~~~~

The version section gives version number of the experiment description
file
