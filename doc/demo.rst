.. _utopya_demo:

Demo project and models
=======================

utopya comes with a `demo project <https://gitlab.com/utopia-project/utopya/-/tree/main/demo>`_ that illustrates how to use utopya in your own projects.
It showcases the following capabilities of utopya:

- Example implementation for a utopya model
  - ``MinimalModel``: using only the minimal amount of utopya features
  - ``ExtendedModel``: showcasing more utopya features, using the :py:mod:`utopya_backend` and one of its ``BaseModel`` classes for a scaffolding of your own model.
  - ``EvalOnlyModel``: a model that only uses the evaluation routines of utopya (and does not have an executable that generates simulation output).
- Creating a ``.utopya-project.yml`` file for project registration.
- Creating a ``<model_name>_info.yml`` file for model registration.
- Adding supplementary files:
  - Project-level updates to the :py:class:`~utopya.multiverse.Multiverse` configuration
  - A project-level base plot configuration pool

Below, you will find more information about the demo project and how it can be used as a blue print for your own utopya-based project.

.. contents::
    :local:
    :depth: 2

----

Instructions
------------
First, install utopya according to the :ref:`installation instructions <installation>`.
If all went well, you should be able to call ``utopya --help`` in your virtual environment.

Afterwards download this ``demo`` directory to a place of your choice and rename it; this will be the place where your own project and model will be implemented.
The files in this directory will be adjusted bit by bit to fit your project and model implementation.

.. hint::

    Instead of copying the ``demo`` directory and making manual adjustments, you can also use the `Python Model Template <https://gitlab.com/utopia-project/models_template_py>`_ to generate your demo repository, which is much easier.
    Follow the instructions given in its README to quickly create your own utopya models repository.
    For more information, also see :ref:`template_project`.

    The text below provides additional background on the ins and outs of such a project repository.



Project setup
-------------
A project in utopya denotes an aggregation of model implementations.
These models may be grouped into a project because they use the same infrastructure and dependencies, address similar questions, or for any other reason.
Correspondingly, utopya attaches some functionality to a project that can be shared between models, like default configurations for simulations or data evaluation.

In order to coordinate project-level functionality, utopya needs to know about the structure of a project.
This is achieved via the ``.utopya-project.yml`` file, which contains project-level information: the project name, local paths, and metadata.

.. admonition:: Demo project file
    :class: dropdown

    .. literalinclude:: ../demo/.utopya-project.yml
        :language: yaml


Project registration
^^^^^^^^^^^^^^^^^^^^
Next step is to let utopya know about the project.
To register your project with utopya, follow these steps:

#. Make sure your project directory is in the intended location and named to your liking.
#. Open the ``.utopya-project.yml`` file and edit the following entries:
    - ``project_name``: This should be the name of *your* project
    - ``paths``: Make sure the ``models_dir`` points to the right directory (relative to the info file).
      If you do not intend on using Python model tests and custom plot implementations, delete the corresponding entries.
    - ``metadata``: Adjust (or delete) the entries (but keep the ``metadata`` mapping, even if it is empty).
#. Enter your project directory and *from that directory* invoke the utopya CLI to register the project:

.. code-block:: bash

    utopya projects register .

You should get a positive response from the utopya CLI and your project should appear in the project list when calling:

.. code-block:: bash

    utopya projects ls

.. note::

    Any changes to the project info file need to be communicated to utopya by calling the registration command anew.
    You will then have to additionally pass the ``--exists-action overwrite`` flag, because a project of that name already exists.
    See ``utopya projects register --help`` for more information.

.. hint::

    **Recommended:** Use the ``--with-models`` flag to register models alongside the project:

    .. code-block:: bash

        utopya projects register . --with-models

    This will search for all ``*_info.yml`` files within the project's ``models`` directory and use those for registration of the individual models.
    If using this command, there is no need to register the models individually below.


Model setup
-----------
Let's get to the model implementation.

Again, utopya needs to know about the model and the corresponding files.
Like with projects, models can be registered using the CLI and an info file, here the ``<model_name>_info.yml`` file.

The ``MinimalModel``
^^^^^^^^^^^^^^^^^^^^
As an example, let's register the ``MinimalModel``:

#. Enter the ``demo/models/MinimalModel`` directory
#. Call the registration command:

    .. code-block:: bash

        utopya models register from-manifest *_info.yml

After successful registration, you should be able to run the model:

.. code-block::

    utopya run MinimalModel

The ``ExtendedModel``
^^^^^^^^^^^^^^^^^^^^^
The ``ExtendedModel`` is a demo for a more complex model implementation.
Additionally, it also uses more features of utopya.
Key differences to the ``MinimalModel`` are:

- The implementation is split up into an ``impl`` *package* and a ``run_model.py``, that invokes the implementation.
- It implements the ``ExtendedModel`` class by inheriting from :py:class:`~utopya_backend.model.step.StepwiseModel` which takes care to implement all the simulation infrastructure and a step-wise model abstraction:
  - Shared PRNG and logger instances.
  - Logic to evaluate the ``write_every`` and ``write_start`` parameters that can be set via the utopya CLI.
  - A ``monitor`` method that communicates simulation progress to the frontend.
  - Abstractions for a modelling paradigm with stepwise iterations of constant time deltas, controlled by ``num_steps``, ``write_start`` and ``write_every``.
- The ``model_plots`` and ``model_tests`` are in use.
- The ``cfgs`` directory contains so-called *config sets* which can be used to define certain sets of default run and evaluation configurations.
- The manifest file holds more information, e.g. on the location of the ``model_plots`` and ``model_tests`` directories.

To register and run it, we can again use its manifest file (and an extended glob pattern that actually matches *all* manifest files):

.. code-block:: bash

    cd demo/
    utopya models register from-manifest **/*_info.yml --exists-action overwrite
    utopya run ExtendedModel

.. note::

    The ``--exists-action`` option is required because the ``MinimalModel`` was already registered and needs to be overwritten or updated.

.. warning::

    Depending on your shell, the ``**/*_info.yml`` glob pattern may not work.

.. hint::

    The ``utopya models register from-manifest`` command is most useful when registering a single or only a few models.
    For all models within a project at once, use the project-based model registration:

    .. code-block:: bash

        cd demo/
        utopya projects register . --with-models --exists-action overwrite


The ``EvalOnlyModel``
^^^^^^^^^^^^^^^^^^^^^
The ``EvalOnlyModel`` shows how utopya can be set up *only* with the evaluation routine being used.
Essentially, the ``utopya run`` command is not available for this model; only ``utopya eval`` can be used.

Key differences to the previous models are:

- There is no executable that generates simulation data, assuming that the evaluation pipeline does not require that.
- Effectively, the model consists only of a bunch of configuration files which define which plots are to be created.
- The ``model_plots`` are also in use, but ``model_tests`` are not.
- The model manifest defines an additional config file, the ``mv_updates.yml`` which can be used to update the :py:class:`~utopya.multiverse.Multiverse` :ref:`meta configuration <mv_meta_cfg>`
  - Here, this file is used to *clear* the so-called *load configuration*, thus leading to no simulation data being expected (which is necessary, because there is no executable that would create output).
  - The load configuration can also be adjusted to load different kinds of data, e.g. from a fixed directory path. Refer to `the dantro docs <https://dantro.readthedocs.io/en/latest/data_io/data_mngr.html#the-load-configuration>`_ for more information.

Essentially, the behavior of this model is equivalent to that of a regular model, only with a few features deactivated.
Thus, to follow the overall paradigm of utopya, some manual steps need to be taken to run the evaluation routine:

- Manually create a model output directory ``~/utopya_output/<model_name>`` (or in the respective other place if you have adjusted it)
- In that directory, create a new directory that follows the timestamp format of the regular run directory, ``YYMMDD-HHMMSS`` or ``YYMMDD-HHMMSS_some-comment``, e.g. ``230101-000000``
- That directory *can* be empty, but it may also contain data that you would like to have loaded, e.g. in a ``data`` subdirectory.

Now you can run the evaluation routine simply via:

.. code-block:: bash

    utopya eval EvalOnlyModel

As is the case with all other models, this will create output in the ``eval/<timestamp>`` subdirectory of the selected run directory.

.. admonition:: Is this really a "model"?
    :class: dropdown

    In utopya, "model" essentially denotes the name of some processing pipeline that *may* start with generating simulation data from some model implementation.
    In a strict sense, referring to a pipeline without that model implementation as "model" can be confusing; however, as the same paradigm is followed, the pipeline is still referred to as "model" in utopya.



Your own model
--------------
For your own model, do the following:

#. Create a new directory within the ``models`` directory (or the corresponding directory defined in the project info file).
#. Add an info file akin to ``MinimalModel_info.yml``, changing the following entries:

  - ``model_name``: should be the name of *your* model
  - ``paths``: adapt the entries here, specifically that for ``executable`` and ``default_cfg``. These can also be paths relative to the info file.
  - ``metadata``: update or delete the entries in there.

#. Make sure you are in the correct directory and call the registration command:

    .. code-block:: bash

        utopya models register from-manifest *_info.yml

Your own model should now be registered and invokable via ``utopya run``.

.. hint::

    **For more complex python models**, we recommended to see how ``ExtendedModel`` includes an implementation package and invokes it.
    This will make it much easier to grow your project.

.. hint::

    Look at the ``ExtendedModel`` and ``EvalOnlyModel`` for other options on how to structure your project.


Requirements for a model executable
-----------------------------------
The model executable need not be a Python script, it can be *any* executable.
It is a Python script in this example to allow for easy readability, but you can choose any programming language for your model implementation.

In fact, utopya does not pose *any* limitations on the executable: it can essentially do whatever it wants.
Only if you want to use more of utopya's features, complying to a certain behaviour is advantageous – but that is all *optional*.

However, we do suggest that the executable complies to the following:

- It should expect one (and only one) additional argument: the absolute path to the YAML configuration file.
  There will not be any additional arguments to the executable.
- The executable should then load that configuration file, a YAML file, and use some of its information:

  - The ``seed`` entry to set the initial PRNG state; this is in order to increase reproducibility of model simulations.
  - The ``output_dir`` entry for the location of any output files; this is in order to have the output files managed by utopya. If using HDF5 output, consider using the ``output_path``, which is a path to an HDF5 file name inside the output directory.
  - The model configuration which is available under the ``<model_name>`` key, where ``<model_name>`` is given by the ``root_model_name`` key.

.. hint::

    All this (and the optional features outlined below) are implemented in the :py:class:`~utopya_backend.model.base.BaseModel` class.
    If you are implementing your model in Python, consider using that as a starting point instead of re-implementing it all by yourself.

Examples
^^^^^^^^
As you may have seen, the ``ExtendedModel`` has a separate file called ``run_model.py`` which is used as a model executable, while the actual implementation is done in the ``impl`` package.
This structure is useful if your model implementation gets more complicated.

Now, the ``impl`` package is never installed, but it needs to be importable from the model executable.
In Python, the ``__main__`` module cannot do relative imports, so a helper function, :py:func:`~utopya_backend.tools.import_package_from_dir`, is used to make the package accessible.

.. admonition:: Generic model executable
    :class: dropdown

    The following ``run_model.py`` file can be used as a model executable if:

    - The file is on the same level as a model implementation package called ``impl``
    - The model class is available as ``impl.Model``

    If this is not the case, simply adjust the corresponding lines:

    .. literalinclude:: ../demo/models/ExtendedModel/run_model.py
        :language: python

    .. hint::

        Do not forget to mark the executable ... as executable:

        .. code-block:: bash

            chmod +x run_model.py

Optional features
^^^^^^^^^^^^^^^^^
*Optionally*, the following information from the config file can be taken into account to use more features of utopya:

- ``log_levels``: provides log levels for the ``backend`` and ``model`` loggers, also adjustable via the CLI.
- For step-based models:
    - ``num_steps``: the number of iterations, which can then be set directly from the CLI.
    - ``write_every`` and ``write_start``: for controlling the time steps at which data is written.
- Signal handling: To shut down gracefully, your simulation should listen to ``SIGTERM`` and ``SIGINT`` and end the simulation within a grace period (few seconds).
  To handle :ref:`stop conditions <stop_conds>`, it should listen to ``SIGUSR1``.

Also, the model may communicate its progress by emitting lines via STDOUT, which is picked up by utopya and translated into a simulation progress bar; this is the so-called **monitoring** feature.
To use monitoring, the output should match the following pattern:

.. code-block:: text

    !!map {progress: 0.01}

Here, ``progress`` denotes the individual simulation's progress and needs to be a float value between 0 and 1.
On utopya side, that line is interpreted as YAML and turned into a dict.

There can also be further entries in the monitor dict which are picked up by the frontend and evaluated via :ref:`stop conditions <stop_conds>`.

.. note::

    Make sure the monitor output appears on a single line, without any line breaks.
    Otherwise the frontend will not be able to parse it.

Data evaluation pipeline
""""""""""""""""""""""""
Being aware of where the model outputs its simulation data, utopya can initiate a data processing pipeline.
To that end, the following configuration files need to be added or adapted:

.. todo:: Work in Progress 🚧


Remarks
^^^^^^^
- Strictly speaking, utopya does not require a model to be associated with a project.
  However, this makes many aspects of simulation control more convenient, which is why we recommend registering a project with utopya.
- Across utopya, there can be multiple models with the same name, e.g. if you want to run multiple versions of a model.
  Models can be distinguished via their ``label`` property, which can also be set via the CLI.
  If there is only one label available, that one will be used automatically; otherwise you might have to choose between "info bundles" using the ``--label`` CLI option.
