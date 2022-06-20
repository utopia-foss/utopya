Welcome to utopya's documentation!
==================================

The :py:mod:`utopya` package provides a simulation management and evaluation framework.
Features include the following:

- Provide model configuration with several default levels
- Project and framework handling
- A powerful CLI to run and evaluate models
- Executing model simulations in parallel and on cluster architectures
- Managing data output directories
- Interfacing with the [dantro] data processing pipeline

It evolved as part of the `Utopia Project <https://utopia-project.org/>`_ and provides the frontend of the `Utopia modelling framework <https://gitlab.com/utopia-project/utopia>`_, a modelling framework for complex and adaptive systems.

Having been outsourced from that project, it can be used with arbitrary model implementations with a very low barrier for entry:
In the simplest case, only the path to an executable is required to run simulations.
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

.. TODO add how-to-cite

.. toctree::
    :caption: Reference
    :maxdepth: 2
    :hidden:

    API Reference <api/utopya>
    LGPLv3 License <https://www.gnu.org/licenses/lgpl-3.0.html>
    index_pages
