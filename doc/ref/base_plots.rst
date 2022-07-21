
.. _utopya_base_plots_ref:

Base Plot Configuration Pool
============================
This page documents utopya's base plot configuration pool which is used for aggregating a plot configuration using `multiple inheritance <https://dantro.readthedocs.io/en/latest/plotting/plot_manager.html#plot-configuration-inheritance>`_.

The entries below are sorted by segments and are using dantro's `naming convention <https://dantro.readthedocs.io/en/latest/plotting/plot_manager.html#base-plots-naming-conventions>`_.
Some sections are still empty, meaning that utopya does not define new entries there.

.. note::

    **Important:** All entries here are **in addition** to the `dantro base plots configuration pool <https://dantro.readthedocs.io/en/latest/data_io/data_ops_ref.html>`_.

    More precisely, the utopya base plots config pool *requires* the dantro base plots config, as it `inherits <https://dantro.readthedocs.io/en/latest/plotting/plot_manager.html#plot-configuration-inheritance>`_ some entries using ``based_on``.

.. hint::

    To quickly search for individual entries, the search functionality of your browser (``Cmd + F``) may be very helpful.
    Note that some entries (like those of the YAML anchors) may only be found if the :ref:`complete file reference <utopya_base_plots_ref_complete>` is expanded.

.. contents::
    :local:
    :depth: 2

----


``.defaults``: default entries
------------------------------

.. literalinclude:: ../../utopya/cfg/base_plots.yml
    :language: yaml
    :start-after: # start: .defaults
    :end-before: # ===



``.creator``: selecting a plot creator
--------------------------------------
More information: :ref:`plot_creators`

.. literalinclude:: ../../utopya/cfg/base_plots.yml
    :language: yaml
    :start-after: # start: .creator
    :end-before: # ===


``.plot``: selecting a plot function
------------------------------------
More information:

- :ref:`plot_func`
- :ref:`pcr_pyplot_plot_funcs`

.. literalinclude:: ../../utopya/cfg/base_plots.yml
    :language: yaml
    :start-after: # start: .plot
    :end-before: # ===


``.style``: choosing plot style
-------------------------------
More information: :ref:`pcr_pyplot_style`

.. literalinclude:: ../../utopya/cfg/base_plots.yml
    :language: yaml
    :start-after: # start: .style
    :end-before: # ===


``.hlpr``: invoking individual plot helper functions
----------------------------------------------------
More information: :ref:`plot_helper`

.. literalinclude:: ../../utopya/cfg/base_plots.yml
    :language: yaml
    :start-after: # start: .hlpr
    :end-before: # ===


``.animation``: controlling animation
-------------------------------------
More information: :ref:`pcr_pyplot_animations`

.. literalinclude:: ../../utopya/cfg/base_plots.yml
    :language: yaml
    :start-after: # start: .animation
    :end-before: # ===


``.dag``: configuring the DAG framework
---------------------------------------
More information:

- :ref:`dag_framework`
- :ref:`plot_creator_dag`

.. literalinclude:: ../../utopya/cfg/base_plots.yml
    :language: yaml
    :start-after: # start: .dag
    :end-before: # ===


``.dag.meta_ops``: meta operations
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The following entries can be included into a plot configuration to make pre-defined :ref:`meta-operations <dag_meta_ops>` available for the data transformation framework.

.. literalinclude:: ../../utopya/cfg/base_plots.yml
    :language: yaml
    :start-after: # start: .dag.meta_ops
    :end-before: # ===


----

.. _utopya_base_plots_ref_complete:

Complete File Reference
-----------------------

.. toggle::

    .. literalinclude:: ../../utopya/cfg/base_plots.yml
        :language: yaml
        :end-before: # end of utopya base plots
