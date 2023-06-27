# Guide to write your own task

## What happens when running an IBL task ? 

1.  the task constructor gets called, this method:
    - reads-in settings: hardware settings and iblrig settings
    - reads-in the task parameters
    - instantiates the hardware mixins
2. The task starts using the `run()` method. Before running, the method:
    - starts the hardware modules
    - creates a session folder
    - saves the parameters to disk
3. The experiment runs: the `run()` method calls the child class `_run()` method
    - this is usually a loop that instantiates a bpod state machine for each trial and runs it
4. After SIGINT or when the maximum number of trials is reached, the experiment stops. The end of the `run()` method:
    - saves the final parameter file
    - registers water administred and session performance to Alyx
    - stops the mixins.
    - initiate local server transfer

## How to write a task

### iblrig.base_tasks.BaseTask
This is the base class for all tasks. It provides abstract methods and methods to create the folder architecture and for the Alyx database registration.
When subclassing BaseTask, you must override the following methods:
-   `_run()`: This is the main method of the task. It is wrapped into by the run() method that provides the folder creation and Alyx interface before and after the task run.
-  `start_hardware()`: This method starts the hardware modules and connects to each one of them.

### Hardware modules
Hardware mixins, in `iblrig.base_tasks` are dedicated to specific modules. These are mixin classes that provide hardware-specific functionality. To use those mixins, compose them with the `BaseClass` above.
The mixins for hardware modules provide a way to decouple the hardware-specific code from the task code.
-   The init_mixin_*() methods are called at instantiation, so they need to work regardless of whether the hardware is connected or not.
-   The start_mixin_*() methods are called at the beginning of the run() method, so they need to ensure that the hardware is properly connected.
-   The stop_mixin_*() methods are called at the end of the run() method, so they need to ensure that the hardware is properly disconnected.
To test only the hardware, you can instantiate the task and call the start_hardware() and stop_hardware() methods.

### iblrig.base_choice_world.ChoiceWorld
This is a subclass of BaseTask that implements the IBL decision-making task family.
When subclassing ChoiceWorld, you must override the following methods:
-   `next_trial()`
