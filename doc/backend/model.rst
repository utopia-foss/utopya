.. _backend_model:

Model base classes
==================


.. contents::
    :local:
    :depth: 2


.. _backend_basemodel:

``BaseModel`` class
-------------------
The :py:class:`~utopya_backend.model.base.BaseModel` implements basic simulation infrastructure like a shared logger, RNG, config file reading, signal handling and abstract methods that provide a blue print for model implementation.

Relevant properties
^^^^^^^^^^^^^^^^^^^

.. todo:: 🚧


Random Number Generator
^^^^^^^^^^^^^^^^^^^^^^^
Via :py:meth:`~utopya_backend.model.base.BaseModel.rng`, the model's own random number generator can be accessed.
Being seeded (with the ``seed`` parameter), this ensures that a simulation is reproducible.

.. note::

    During setup (:py:meth:`~utopya_backend.model.base.BaseModel._setup_rng`), the system's and numpy's *default* RNGs are also seeded (via :py:func:`random.seed` and :py:func:`numpy.random.seed`, respectively).
    This is done to ensure that simulations are deterministic even if *not* using the model's own RNG instance, which is not always possible.

    To not set those seeds in a simulation, set the ``seed_numpy_rng`` and ``seed_system_rng`` parameters to False:

    .. code-block:: yaml

        parameter_space:
          seed: 123
          seed_numpy_rng: false   # if true: will use (seed + 1 = 124)
          seed_system_rng: false  # if true: will use (seed + 2 = 125)


.. _backend_stepwisemodel:

``StepwiseModel`` class
-----------------------
The :py:class:`~utopya_backend.model.step.StepwiseModel` specializes the :py:class:`~utopya_backend.model.base.BaseModel` for models that abstract model iteration to step-wise integration with integer time steps.

An example for a model based on ``StepwiseModel`` can be found in the :ref:`utopya demo project <utopya_demo>`:


Example implementation
^^^^^^^^^^^^^^^^^^^^^^
The following is the full implementation of ``ExtendedModel``, one of the :ref:`utopya demo models <utopya_demo>`.
It inherits from :py:class:`~utopya_backend.model.step.StepwiseModel` and implements the following methods:

- ``setup``: Reads configuration entries and sets up output datasets
- ``perform_step``: Iterates the state
- ``monitor``: Provides monitoring information to utopya
- ``write_data``: Writes data

.. toggle::

    .. literalinclude:: ../../demo/models/ExtendedModel/impl/model.py
        :language: python

See the ``demo`` directory `in the repository <https://gitlab.com/utopia-project/utopya/-/tree/main/demo>`_ for the context in which this model is implemented.
Alternatively, have a look at the :ref:`utopya_demo` page.
