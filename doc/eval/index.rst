.. _eval:

Evaluating Simulations
======================

The :py:mod:`utopya.eval` subpackage is all about evaluating your simulation data.
It implements a :py:mod:`dantro`-based data processing pipeline that allows to load, process and visualize simulation output.

While this part of the documentation is being worked on, please refer to the respective section in the `Utopia Documentation <https://docs.utopia-project.org/html/usage/eval/index.html>`_.
Apart from differing model names, all aspects of the `plotting tutorial <https://docs.utopia-project.org/html/usage/eval/plotting/index.html>`_ also apply to other utopya-based models.


Plot Functions
--------------
In :py:mod:`utopya.eval`, a number of plot functions are defined that are tailored to certain simulation types.
For instance, the ``.plot.ca`` (see :ref:`plot_funcs_ca`) function specializes on visualizing Cellular Automata data.

.. toctree::
    :maxdepth: 2

    plot_funcs
