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


.. admonition:: Specifying properties for hexagonal grid structure

    To plot hexagonal grids, more information is required than for square grids;
    :py:func:`~utopya.eval.plots.ca.imshow_hexagonal` documents which parameters are needed.

    This information can be specified via the plot configuration or alongside the data as *metadata attributes*.
    The latter approach is preferable, because it is self-documenting and reduces future errors.

    If you store that information **alongside the data**, it needs to be accessible via the :py:attr:`xarray.DataArray.attrs` of the data passed to :py:func:`~utopya.eval.plots.ca.caplot`.
    Depending on your data source, there are different ways to achieve this.

    * For xarray objects, simply use assignments like ``my_data.attrs["pointy_top"] = True``.
    * If your data is loaded from HDF5 datasets into the :py:class:`~utopya.eval.datamanager.DataManager`, the dataset attributes are automatically carried over.

    If you want to pass grid properties **via the plot configuration**, they need to be passed through to :py:func:`~utopya.eval.plots.ca.imshow_hexagonal`, which can happen either via the `default_imshow_kwargs` argument or individually within `to_plot`:

    .. toggle::

        .. code-block:: yaml

            my_hexgrid_plot:
              # ... same as above ...
              grid_structure: hexagonal

              default_imshow_kwargs:  # passed to *all* imshow_hexagonal invocations
                grid_properties:
                  coordinate_mode: offset
                  pointy_top: true
                  offset_mode: even
                  # ...

              to_plot:
                some_data:
                  # ...
                  imshow_kwargs:      # passed to this specific imshow_hexagonal invocation
                    grid_properties:
                      # ...

.. hint::

    For an excellent introduction to hexagonal grid representations, see `this article <https://www.redblobgames.com/grids/hexagons/>`_.





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
