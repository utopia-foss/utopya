.. _run:

Running Simulations
===================

Performing simulation runs is at the center of :py:mod:`utopya`'s capabilities.

This page gives an overview of how this is achieved, mainly linking to the various parts of utopya.
Please refer to the `Utopia documentation <https://docs.utopia-project.org/html/usage/run/index.html>`_ for examples on how to perform simulation runs.

Briefly:
A simulation run is orchestrated by a :py:class:`~utopya.multiverse.Multiverse` instance. It orchestrates all the various aspects of configuring, performing and evaluating a simulation:

* It constructs a meta-configuration for the new run, see :ref:`cfg`.
* Depending on the configured model parameter space, a :py:class:`~utopya.task.WorkerTask` is added for each so-called universe that should be simulated.
* It sets up a :py:class:`~utopya.workermanager.WorkerManager` which will carry out the actual simulation tasks in a parallel or distributed fashion.
* A :py:class:`~utopya.reporter.WorkerManagerReporter` reports on the progress of a simulation.
* For later on loading the simulation output, a :py:class:`~utopya.eval.datamanager.DataManager` is created.
* Processing and visualization of that data is then managed by the :py:class:`~utopya.eval.plotmanager.PlotManager`.



----

.. toctree::
    :maxdepth: 2

    run
    distributed


.. todo::

    This part of the docs is *Work In Progress* 🚧
