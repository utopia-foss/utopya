
.. _distributed_runs:

Distributed Simulation Runs
===========================

By default, :ref:`simulation runs <running_simulations>` occur on a single machine: all configured simulation tasks are carried out.

However, with a large parameter space or long-running individual universes, utopya allows to perform simulation runs in a *distributed* fashion, making use of the computational resources of multiple machines.

These approaches differ in their requirements on how the distributed machines may communicate with each other.
The :py:class:`~utopya.multiverse.DistributedMultiverse` is where this functionality is implemented.


.. _join_run:

Joining Runs
------------

In utopya, "joining" a simulation run means:

* You started a simulation on machine A simply via ``utopya run --skippable``
* You have one or more machines B1, B2, ... that should help in performing that run; you use ``utopya join-run`` to let them join.

Effectively, all involved machines work together in covering the defined parameter space, thus finishing the simulation faster.

To allow this, the :py:class:`~utopya.multiverse.Multiverse` and :py:class:`~utopya.multiverse.DistributedMultiverse` instances take a more lenient approach on what happens if a universe output directory (folders like ``<out_dir>/data/uni123``) already exists: they assume that some other Multiverse has already grabbed that task and is working on it, meaning that they don't need to work on it and will *skip* the task.
Essentially, the content of the ``data`` directory is used as a way of communicating about tasks that are already being worked on, hence allowing other Multiverse instances to skip those tasks.

.. note::

    ``utopya join-run`` requires a data directory that is *shared* among the distributed machines, e.g. a network drive.

    Ideally, the drive is configured such that there is file locking, preventing multiple machines to create the same folder or file.

.. note::

    For ``utopya join-run`` to work, the main simulation needs to be invoked with the ``skippable.enabled`` flag set.
    This can be done via the CLI flag ``--skippable`` or, more permanently, via additional entries in the :ref:`user <mv_meta_cfg_layer_user>` or :ref:`project configuration <mv_meta_cfg_layer_framework_and_project>`:

    .. code-block:: yaml

        # At the top level of the meta-configuration, set:
        skipping:
          enabled: true

🚧 ...

See also:
* CLI: ``utopya join-run --help``
* :py:meth:`utopya.multiverse.DistributedMultiverse.join_run`



.. _run_existing:

Running Existing Simulations
----------------------------

It is sometimes desirable to repeat simulation runs, e.g. because a simulation failed due to outside circumstances.
This can be achieved using the ``utopya run-existing`` CLI command.

For a regular simulation or when joining a simulation run, the universe output directories and config files are created only when a task is being taken up and worked on.
In contrast, when running an existing simulation, these folders, configuration files, or even simulation output may already exist.
Hence, when repeating a simulation, it is possible to either skip folders with existing universe output — or delete that output and run them anew.

Consider this a two-step procedure:

#. First, ``utopya run`` is used to create define a Multiverse run.
   This run may be carried out completely, partially, or (deliberately) not at all.
#. In a second step, ``utopya run-existing`` is used to (re-)run individual or all universes.

To achieve this, the :py:class:`~utopya.multiverse.DistributedMultiverse` loads the existing meta-configuration.
Depending on whether all or only a selection of tasks should be carried out, it adds the appropriate tasks.
When a task is grabbed, its setup function checks if the universe directory, its configuration or any output files already exist; it then acts accordingly by either skipping the simulation, clearing the output, or starting a simulation from scratch.


.. note::

    In a HPC cluster setting with a job scheduler, the following procedure can be useful:

    * Use ``utopya run --skip-after-setup`` to create all universe output directories.
    * Then use a bash script to determine all the universe IDs from the ``data`` directory.
    * Use those universe IDs to invoke many independent simulation tasks: ``utopya run-existing --uni 123``, where ``123`` should be replaced with the respective universe IDs.

    This way, the job scheduler has full control over the execution of universe tasks, not the ``Multiverse``, which can be a benefit in some cases.


See also:
* CLI: ``utopya run-existing --help``
* :py:meth:`utopya.multiverse.DistributedMultiverse.run`



.. _cluster_mode:

Cluster Mode
------------

The utopya cluster mode can be used in the following scenario:

* A run is started via a queueing system and on many identical (or very similar) compute nodes.
* On each compute node, a single :py:class:`~utopya.multiverse.Multiverse` is started, with ``cluster_mode: true``.
* The individual compute nodes can locate themselves in a list of all involved compute nodes; depending on the position in that node list, they take up a certain slice of the parameter space and work only on that part.

The advantages of this scenario are:
* Multiverse instances are truly independent and do not need to communicate at all.
* Multiverses can use fast local storage to write simulation output, instead of needing to write to some shared mount point.

Disadvantages are:
* With very heterogeneous run times, resources may not be allocated ideally.
* The setup requires a job scheduler and the respective batch scripts, producing some overhead.

🚧 ...
