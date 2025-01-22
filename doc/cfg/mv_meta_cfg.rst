.. _mv_meta_cfg:

Multiverse Meta-Configuration
=============================

.. todo:: Work in Progress 🚧

.. contents::
    :local:
    :depth: 2


.. _mv_meta_cfg_layers:

Configuration Layers
--------------------
The final Multiverse meta-configuration is built by recursively updating the base configuration with successive configuration files, if they are present.

.. _mv_meta_cfg_layer_base:

Base
""""
The :ref:`utopya base configuration <utopya_base_meta_cfg>` defines the starting point for the meta-configuration.
It aims at providing good default values and also documenting the possible configuration options.


.. _mv_meta_cfg_layer_framework_and_project:

Framework & Project
"""""""""""""""""""
Both at the framework and the project level, additional configuration files can be specified.

For instance, if using `Utopia <https://utopia-project.org/>`_ as a framework to implement C++ models, it supplies a `configuration file <https://gitlab.com/utopia-project/utopia/-/blob/master/python/utopia_mv_cfg.yml>`_ that specifies configuration entries that are required for C++-based models.

After framework-specific updates were carried out, the project can do the same.

To define framework- and project-specific update configurations, add the ``paths.mv_project_cfg`` key in the respective ``.utopya-project.yml`` files:

.. code-block:: yaml

    paths:
      # Path to project-level default configuration for Multiverse
      mv_project_cfg: cfg/mv_project_cfg.yml


.. _mv_meta_cfg_layer_model_mv:

Model-specific
""""""""""""""
Models can *also* specify updates to the meta-configuration (not only the model-related default values, see :ref:`below <mv_meta_cfg_layer_model_defaults>`).

To define a model-specific update configuration, add the ``paths.mv_model_cfg`` key in the respective ``<ModelName>_info.yml`` file:

.. code-block:: yaml

    paths:
      # Path to model-specific Multiverse configuration updates
      mv_model_cfg: MyModel_mv_update_cfg.yml


.. _mv_meta_cfg_layer_user:

User Configuration
""""""""""""""""""
A user-specific configuration, typically stored in ``~/.config/utopya/user.yml``.
These are applied to *all models* and *all projects* that are invoked from that user's account.

The file can be accessed and edited also via the CLI:

.. code-block:: bash

    utopya config user --help


.. _mv_meta_cfg_layer_model_defaults:

Model Defaults
""""""""""""""
Each model defines the default *model* parameters in their model configuration.

Unlike all other configuration layers, the model defaults do not update the *whole* meta-configuration, but only the ``parameter_space.<ModelName>`` entry.


.. _mv_meta_cfg_layer_run_cfg_and_cfg_sets:

Run Config & Config Sets
""""""""""""""""""""""""
The run configuration is a configuration file that is used for a specific run.
It is the "last" layer of file-based updates.

When calling ``utopya run``, the configuration file can be passed either as a file path — or, alternatively, by means of so-called :ref:`configuration sets <utopya_cfg_sets>` that can be accessed by an alias.


.. _mv_meta_cfg_layer_updates:

CLI Updates
"""""""""""
Some parameters can be defined via the CLI directly and are the very last recursive update procedure before arriving at the final meta-configuration.

For instance, when calling

.. code-block:: bash

    utopya run MyModel -W 12 -N 4k --mp my_param=123

there are three CLI-based updates to the meta configuration:

.. code-block:: yaml

    worker_manager:
      num_workers: 12

    parameter_space:
      num_steps: 4k

      MyModel:
        my_param: 123
