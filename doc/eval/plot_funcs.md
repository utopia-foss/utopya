# Plot Functions

utopya provides a number of additional plot functions over those already made available via {py:mod}`dantro`:

```{contents}
:local:
:depth: 2
```

---

## `.plot.ca`: Visualize CA
The {py:func}`~utopya.eval.plots.ca.caplot` function, accessible via the `.plot.ca` base configuration, is specialized to visualize time series of cellular automata (CA) data.

To select this plot function, the following configuration can be used as a starting point:

```yaml
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
```

For more information, see


### Square grids
Typically, CA use a grid discretization with square cells:

```{image} ../_static/_gen/caplot/snapshot_square.pdf
:target: ../_static/_gen/caplot/snapshot_square.pdf
:width: 100%
```

```{raw} html
<video width="720" src="../_static/_gen/caplot/anim_square.mp4" controls></video>
```


### Hexagonal grids  
For CA grids with hexagonal cells, the {py:func}`~utopya.eval.plots.ca.imshow_hexagonal` function can; see docstring for more information.

`````{admonition} Specifying properties for hexagonal grid structure

To plot hexagonal grids, more information is required than for square grids;
{py:func}`~utopya.eval.plots.ca.imshow_hexagonal` documents which parameters are needed.

Aside from adding the that information to the selected data as attributes, it can also be specified via the plot configuration.
The arguments need to be passed through to {py:func}`~utopya.eval.plots.ca.imshow_hexagonal`, which can happen either via the `default_imshow_kwargs` argument or individually within `to_plot`:

````{toggle}
```yaml
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
```
````
`````

The output (for the same dummy data as used above) may look like this:

```{image} ../_static/_gen/caplot/snapshot_hex.pdf
:target: ../_static/_gen/caplot/snapshot_hex.pdf
:width: 100%
````

```{raw} html
<video width="720" src="../_static/_gen/caplot/anim_hex.mp4" controls></video>
```


---

## `.plot.facet_grid` extensions

### `.plot.facet_grid.imshow_hexagonal`
Brings faceting support to {py:func}`~utopya.eval.plots.ca.imshow_hexagonal`:

```{image} ../_static/_gen/plots/imshow_hexagonal_fg.pdf
:target: ../_static/_gen/plots/imshow_hexagonal_fg.pdf
:width: 100%
````


---

## `.plot.graph`: Plot graphs

Invokes {py:func}`~utopya.eval.plots.graph.draw_graph`.

```{todo}
🚧
```


---

## `.plot.snsplot`: Plot using seaborn

Invokes {py:func}`~utopya.eval.plots.snsplot.snsplot`.

```{todo}
🚧
```
