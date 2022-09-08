.. _eval_plot_funcs:

Plot Functions
==============

utopya provides a number of additional plot functions over those already made available via :py:mod:`dantro`.

.. contents::
    :local:
    :depth: 2

----

.. _plot_funcs_ca:

``.plot.ca``: Visualize Cellular Automata (CA)
----------------------------------------------
The :py:func:`~utopya.eval.plots.ca.caplot` function, accessible via the ``.plot.ca`` base configuration, is specialized to visualize time series of cellular automaton (CA) data.

To select this plot function, the following configuration can be used as a starting point:

.. code-block:: yaml

    my_ca_plot:
      based_on:
        - .creator.pyplot       # or some other creator
        - .plot.ca              # select the CA plotting function

      select:                   # specify which data to select
        some_data:
          path: path/to/some/data

      to_plot:                  # and which data to plot
        some_data:
          title: some custom title
          cmap: inferno
          limits: [min, max]
          # ... more arguments here, see docstring

For more information, see below.


Square grids
^^^^^^^^^^^^
Typically, cellular automata use a grid discretization with square cells.
The output (as an animation) may look like this:

.. raw:: html

    <video width="720" src="../_static/_gen/caplot/anim_square.mp4" controls></video>

.. _plot_funcs_ca_hex:

Hexagonal grids
^^^^^^^^^^^^^^^
The :py:func:`~utopya.eval.plots.ca.caplot` function integrates :py:func:`~utopya.eval.plots.ca.imshow_hexagonal`, which can plot data from cellular automata that use hexagonal cells.
The output (for the same dummy data as used above) may look like this:

.. raw:: html

    <video width="720" src="../_static/_gen/caplot/anim_hex.mp4" controls></video>

:py:func:`~utopya.eval.plots.ca.imshow_hexagonal` is used for plotting if the ``grid_structure`` argument is set to ``hexagonal`` or if the given data has data attributes that specify that grid structure.

.. hint::

    For an excellent introduction to hexagonal grid representations, see `this article <https://www.redblobgames.com/grids/hexagons/>`_.

.. admonition:: Specifying properties for hexagonal grid structure

    To plot hexagonal grids, more information is required than for square grids;
    :py:func:`~utopya.eval.plots.ca.imshow_hexagonal` documents which parameters are needed.

    This information can be specified via the plot configuration or alongside the data as *metadata attributes*.
    The latter approach is preferable, because it is self-documenting and reduces future errors.

    If you store that information **alongside the data**, it needs to be accessible via the :py:attr:`xarray.DataArray.attrs` of the data passed to :py:func:`~utopya.eval.plots.ca.caplot`.
    Depending on your data source, there are different ways to achieve this.

    * For xarray objects, simply use assignments like ``my_data.attrs["pointy_top"] = True``.
    * If your data is loaded from HDF5 datasets into the :py:class:`~utopya.eval.datamanager.DataManager`, the dataset attributes are automatically carried over.

    If you want to pass grid properties **via the plot configuration**, they need to be passed through to :py:func:`~utopya.eval.plots.ca.imshow_hexagonal`.
    This can happen via multiple arguments:

    - ``default_imshow_kwargs`` is passed to all ``imshow`` or ``imshow_hexagonal`` invocations.
    - ``imshow_hexagonal_extra_kwargs`` is passed *only* to ``imshow_hexagonal`` calls, updating the above.
    - ``imshow_kwargs`` within ``to_plot`` entries are updating the above *for the specific entry*.

    If you want the plot to allow square grid representations, it's best to use the ``imshow_hexagonal_extra_kwargs``.

    .. toggle::

        .. code-block:: yaml

            my_hexgrid_plot:
              # ... same as above ...
              grid_structure: hexagonal

              default_imshow_kwargs: {}       # passed to imshow *and* imshow_hexagonal

              imshow_hexagonal_extra_kwargs:  # passed *only* to imshow_hexagonal
                grid_properties:
                  coordinate_mode: offset
                  pointy_top: true
                  offset_mode: even
                  # ...

              to_plot:
                some_data:
                  # ...
                  imshow_kwargs:              # passed to this specific imshow or imshow_hexagonal call
                    grid_properties:
                      # ...


-----

.. _plot_funcs_abm:

``.plot.abm``: Visualize Agent-Based Models (ABM)
-------------------------------------------------
The :py:func:`~utopya.eval.plots.abm.abmplot` function, accessible via the ``.plot.abm`` base configuration, is specialized to visualize time series of agent-based models (ABM), i.e. the position and certain properties of agents in their domain.

To select this plot function, the following configuration can be used as a starting point:

.. code-block:: yaml

    my_abm_plot:
      based_on:
        - .creator.pyplot       # or some other creator
        - .plot.abm             # select the ABM plotting function

      select:                   # which data to select for plotting
        some_agents:
          path: path/to/some/agent_data

      to_plot:                  # and which data to plot
        some_agents:
          # specify which data variables to use for position and orientation
          x: x
          y: y
          orientation: orientation
          # ... more arguments here, see docstring

      # arguments on this level are shared among all entries in `to_plot`


Example output may look like this:

.. raw:: html

    <video width="720" src="../_static/_gen/abmplot/fish.mp4" controls></video>

.. admonition:: Corresponding plot configuration
    :class: dropdown

    The following configuration was used to generate the above example animation:

    .. literalinclude:: ../../tests/cfg/plots/abm_plots.yml
        :language: yaml
        :start-after: ### START -- doc_fish
        :end-before: ### END ---- doc_fish

    The used dummy data (``circle_walk…``) is an :py:class:`xarray.Dataset` with data variables ``x``, ``y``, ``orientation``, each one spanning dimensions ``time`` and ``agents``.
    Data variables do not have coordinates in this case, but it would be possible to supply some.

.. admonition:: Agents in periodic space

    The ``tail_max_segment_length`` parameter is useful if you plan on drawing tails of agents that move in a periodic space.
    In such a case, agent positions may jump aprubtly when crossing a boundary.
    Ordinarily, this would lead to the tail segment going across the whole domain.

    To avoid this, set the ``tail_max_segment_length`` parameter to half the domain size; this typically suffices to detect jumps in x- or y- position and leads to these segments not being drawn.
    (To be precise, the length refers not to that of the segment but to the differences in x- and/or y-position.)


-----

``.plot.facet_grid`` extensions
-------------------------------

``.plot.facet_grid.imshow_hexagonal``
-------------------------------------
Brings faceting support to :py:func:`~utopya.eval.plots.ca.imshow_hexagonal`:

.. image:: ../_static/_gen/plots/imshow_hexagonal_fg.pdf
    :target: ../_static/_gen/plots/imshow_hexagonal_fg.pdf
    :width: 100%





-----

``.plot.graph``: Plot graphs
----------------------------

Invokes :py:func:`~utopya.eval.plots.graph.draw_graph`.

.. todo:: 🚧






-----

``.plot.snsplot``: Plot using seaborn
-------------------------------------

Invokes :py:func:`~utopya.eval.plots.snsplot.snsplot`.

.. todo:: 🚧
