.. _welcome:

Welcome to utopya's documentation!
==================================

The :py:mod:`utopya` package provides a simulation management and evaluation
framework with the following feature set:

- **Run model simulations** in parallel and on cluster architectures

  - Conveniently perform parameter sweeps of arbitrary parameters with the help
    of the `paramspace <https://gitlab.com/blsqr/paramspace>`_ package.

- A **powerful CLI** to run and evaluate models, including interactive plotting
- Integrates the `dantro <https://gitlab.com/utopia-project/dantro>`_
  **data processing pipeline**:

  - Loads data into a hierarchical data tree, supplying a uniform interface
  - Gives access to a configuration-based **data transformation framework**,
    separating data preprocessing from visualization for increased generality
  - Easy extensibility of plot creators via model-specific plot implementations

- A **versatile configuration interface** for both simulation and evaluation:

  - Assembling multi-level model configurations, including several default
    levels
  - Assembling plot configurations with multiple inheritance, reducing
    redundant definitions

- Model, project, and framework registration and handling
- Managing data output directories
- Tools to simplify model test implementations or working without a CLI
- ... and more

The :py:mod:`utopya` package evolved as part of the
`Utopia Project <https://utopia-project.org>`_ and provides the frontend of
the `Utopia modelling framework <https://gitlab.com/utopia-project/utopia>`_.
Having been outsourced from that project, it can be used with arbitrary model
implementations with a very low barrier for entry: in the simplest case, only
the path to an executable is required to run simulations.
With more compliance to the utopya interface, more features become available.

The :py:mod:`utopya` package is **open source software** released under the `LGPLv3+ <https://www.gnu.org/licenses/lgpl-3.0.html>`_ license.

.. warning::

    This documentation is **WORK IN PROGRESS**.

.. note::

    If you find any errors in this documentation or would like to contribute to the project, we are happy about your visit to the `project page <https://gitlab.com/utopia-project/utopya>`_.

.. ----------------------------------------------------------------------------

.. toctree::
    :hidden:

    Repository <https://gitlab.com/utopia-project/utopya>
    Utopia Project <https://utopia-project.org/>

.. toctree::
    :hidden:

    _to_do

.. TODO add how-to-cite

.. toctree::
    :caption: Reference
    :maxdepth: 2
    :hidden:

    API Reference <api/utopya>
    LGPLv3 License <https://www.gnu.org/licenses/lgpl-3.0.html>
    index_pages
