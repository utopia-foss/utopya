# Changelog

`utopya` aims to adhere to [semantic versioning](https://semver.org/).

## v1.3.0
### Features and enhancements
- !71 allows setting permissions on a simulation's subdirectories.
  Also sets the `eval` directory permissions such that other users of the same group can evaluate simulations without requiring manual permission changes.
- !74 implements `utopya run-existing`, an *experimental* feature that allows finishing or re-running a previously-created simulation run.
- !80 improves the `Reporter` to show host machine information and an overview of task exit codes.

### Bug fixes
- !78 fixes a regression in `.plot.abm` caused by changed `.groupby` operation behaviour in xarray.

### Removals and deprecations
- !72 removes the deprecated CA `ca.state` plot and the `draw_cbar` and `limits` arguments of the `.plot.ca`.

### Internal
- !76 moves the logging-related adjustments (e.g. colored log messages) to their own private module, `utopya._logging`.
- !79 removes testing (and thus official support) for Python 3.8.
- !79 replaces the deprecated `pkg_resources` module with `importlib.resources`.
- !79 adds support for numpy >= 2.0.


## v1.2.13
- !70 adds `utopia` as a console script, giving access to the `utopya` CLI.

## v1.2.12
- !68 lets the `xr.DataArray` underlying `XarrayDC` inherit attributes from the container instance (don't know why that wasn't configured to be the case before).
- !67 fixes a regression in the Read-The-Docs configuration.

## v1.2.11
- !66 fixes a bug in `ModelBenchmarkMixin` that prevented reconstructing a labelled DataArray for evaluation of the cumulative benchmarking results.

## v1.2.10
- !62 adds the `-W`/`--num-workers` option to `utopya run`, a shortcut to more easily set the number of worker processes.
- !63 fixes a YAML loading issue in the `MinimalModel` introduced by `ruamel.yaml >= 0.18`.
- !65 adds test environments for Python 3.12

## v1.2.9
- !61 fixes a bug in graph animation plots that prohibited plotting if additional graph attributes were set.
    - Also reduces the verbosity of the graph plot by hiding repetitive log messages.
- !60 allows controlling how many tasks the `WorkerManager` spawns each iteration of the working loop, improving CPU utilisation when many short simulations need to be started in fast succession.

## v1.2.8
- !58 changes the default behaviour of the `utopya_backend` `BaseModel` to also seed numpy's `np.random` default RNG and the `random` module's default RNG when setting up a model.
  This makes Python simulations deterministic even in cases where an external RNG is being used; *not* having done this in the past meant that simulations would not be reproducible, which is why this is considered a *bug fix*.
  The behaviour can be deactivated by setting `seed_numpy_rng` and `seed_system_rng` parameters to False.
- !59 removes redundant YAML-related code, which is now implemented in the [`yayaml` package](https://gitlab.com/blsqr/yayaml).
- !59 requires [paramspace v2.6](https://gitlab.com/blsqr/paramspace), which includes improvements, bug fixes, and (minor) breaking changes.

## v1.2.7
- !55 improves graph layouting by using the pygraphviz package (instead of the outdated pydot).
  For plotting networks, the utopya installation now includes a set of optional dependencies, installable via `pip install utopya[opt]`.

## v1.2.6
- !57 fixes regressions from updated versions of numpy and pydantic.

## v1.2.5
- !54 fixes a bug in the CLI that prohibited applying configuration updates during interactive plotting (`utopya eval -i <model_name> --update-plots-cfg …`)
- !56 improves an error message that is raised when a model executable is not executable.

## v1.2.4
- !52 fixes a bug in `GraphPlot` that prevented `PlotHelper` invocation during animations.
- !53 implements `ModelBenchmarkMixin` which can be used to easily aggregate information about elapsed times for the different parts of a model iteration.
- !53 allows `BaseModel` to not `sys.exit` on a signal but simply return, configurable via class variable `USE_SYS_EXIT`.


## v1.2.3
- !50 makes model registration easier by adding the `--with-models` flag to the `utopya projects register` command.
- !51 adds CI tests for Python 3.11.


## v1.2.2
- !46 fixes a bug in the ABM plot occurring with the latest xarray version.


## v1.2.1
- !43 allows model-specific updates to the `Multiverse` configuration
- !43 makes specifying a model executable optional, allowing *evaluation only* pipelines.
- !45 implements shell completion for model names, project names, and run directories.


## v1.2.0
- !41 implements `.plot.abm` which specializes on plotting output from agent-based models. Refer to the documentation for more information and examples.


## v1.1.3
- !39 fixes an error where auto-scaling in animated `caplot`s was done despite `vmin` and/or `vmax` being set.
- !40 adds `Parameter` shorthand modes `is-positive-or-zero`, `is-negative-or-zero`, and `is-in-unit-interval`.


## v1.1.2
- !37 fixes `caplot` for hexagonal grid structures, now supporting different hexagon orientations, offset modes and boundary options.
- !37 adds `imshow_hexagonal` as facet grid kind.
- !22 replaces utopya's `ColorManager` with the updated [dantro `ColorManager`](https://dantro.readthedocs.io/en/latest/plotting/color_mngr.html).
- !22 integrates the `ColorManager` into `caplot`, offering more ways to control colormaps and norms and fixing a number of subtle visual bugs.
- !22 fixes a bug in `GridDC` that led to data attributes being lost.
- !22 adds the `debug_level` option to the `Multiverse` and its meta configuration.
    - For now, this does not do a lot, but it will be expanded to control more aspects depending on debug level.
    - With `debug_level >= 2`, Python `DeprecationWarning`s are shown.

### Deprecations
- !22 deprecates the `limits` argument for individual `caplot` properties; use the more conventional `vmin` and `vmax` instead.
- !22 deprecates the `draw_cbar` argument for individual `caplot` properties; use the more conventional `add_colorbar` instead.


## v1.1.1
- !36 fixes a critical bug that prevented installing utopya from PyPI.
- !36 removes minimum versions from requirements, making dependency resolution simpler.


## v1.1.0
### Features and enhancements
- !28 improves error messages upon missing model executable.
- !31 implements the `utopya_backend` package which bundles classes and function that can be used to implement models.
    - `BaseModel` provides shared simulation infrastructure like an RNG, signal handling, loggers, and a general scaffolding for running the model.
    - `StepwiseModel` specializes `BaseModel` for models that make an "integer time" abstraction, with the `perform_step` method describing how to iterate the state.
- !31 improves handling of `WorkerTask`'s that were terminated due to a `StopCondition` signal.
- !32 adds the `utopya test MODEL_NAME` command to the CLI, making it easier to run associated Python model tests.
- !34 expands tests for drawing graphs using `.plot.graph`.

### Bug fixes
- !30 fixes a bug that prevented re-running a `Multiverse` from the backed-up `meta_cfg.yml` file of a previous run.

### Removals and deprecations
- !29 removes the (dysfunctional) `!model` YAML constructor; potentially to be re-added at a later point (discussed in #51).



## v1.0.0
This is the first *standalone* release of utopya.
With the standalone version, utopya can be used in more general contexts: Whenever you need to perform simulation runs from some executable and evaluate its outputs.

Prior to this release, utopya was only available as part of the [Utopia modelling framework](https://gitlab.com/utopia-project/utopia) and could not be used outside of it.

### Features and enhancements
- !1 makes a number of substantial and backwards-incompatible changes that aim to improve package structure and maintainability:
    - Apply code formatting using [black](https://github.com/psf/black)
    - Implement the [pre-commit](https://pre-commit.com) framework to maintain consistent code formatting and allow other pre-commit hooks.
    - Remove old-style plot functions and the legacy transformation framework
    - Improve module structure, particularly by consolidating evaluation-related modules into a submodule
- !2 consolidates functionality related to stop conditions into a single module and provides the `stop_condition_function` decorator to simplify adding custom condition functions.
- !3 provides a demo model that illustrates the utopya model interface
- !3 reworks and simplifies parts of the model registry
    - Require labels for model info bundles and allow specifying a default label
    - Let `exists_action` only act on info bundles, not on model names
- !3 and !4 implement a more modern CLI using [click](https://click.palletsprojects.com/)
    - All functionality is roughly maintained, but CLI syntax has changed in some places.
      The legacy CLI is removed.
    - Makes it much easier to expand the CLI and allows testing using pytest.
    - Improves modularization by moving all CLI-related implementations into the new and separate `utopya_cli` package.
    - Provides more ways to register models. In particular, there is now the option to register a model's metadata via a "model info file".
    - !19 improves the implementation of `utopya models copy`, becoming more language-agnostic and extendable.
- !4 and !6 add a validated project registry, which keeps track of utopya projects (which in turn contain models) and frameworks: two abstraction levels that play a role in determining the configuration hierarchy.
    - !24 improves the registry framework and the CLI to better handle corrupt project (or model) registry files.
- !5 adds changes that allow a proper [outsourcing of utopya from Utopia](https://gitlab.com/utopia-project/utopia/-/merge_requests/277):
    - Extends the project registration CLI with `--require-matching-names` option.
    - Allows to specify custom plot configuration pools via the meta-configuration.
    - Allows to associate a project with a framework project.
    - Adds new framework- and project-level configuration levels that are taken into account when compiling the Multiverse meta-configuration and the base plot configuration pools.
- !6 improves plotting functions:
    - Adds `snsplot` for seaborn-based plots
    - Modernizes the CA plot (`caplot`), now supporting the data transformation framework and deprecating the old `ca.state` plot
- !6 adds an extended demo model that showcases utopya usage for Python-based model implementations.
- !6 moves definition of custom config set search directories to the project-level and extends search to a wider set of model source subdirectories.
- !8 improves the package API documentation and includes intersphinx for cross-referencing to other packages.
- !9 adapts the package structure to the reworked dantro >= v0.18 interface
    - This pertains mostly to the plotting framework. Due to utopya wrapping many parts of that interface, there are few backwards-*incompatible* changes.
    - However, notice the [deprecations](https://gitlab.com/utopia-project/dantro/-/blob/master/CHANGELOG.md#v0180) introduced by dantro v0.18.
- !14 improves plot module pre-loading:
    - Plot modules are now imported at the time of `PlotManager` initialization.
    - Plot modules specified in the project and framework can be pre-loaded as well; this can disabled via the project `settings`.
- !18 expands the `ColorManager`, now allowing to specify continuous colormaps (using [`LinearSegmentedColormap`](https://matplotlib.org/stable/api/_as_gen/matplotlib.colors.LinearSegmentedColormap.html)).
- !21 updates and cleans up the base plots configuration, making use of the newly implemented dantro base plots config pool.
- !23 allows to store a model's project and framework repository states alongside the `Multiverse`'s backup for config files; this can help to reconstruct the state in which a model was run.

### Internal
- !10 outsources `utopya._import_tools` to `dantro._import_tools`




## v0.8.8
This is the version number of `utopya` at the time it was outsourced from the Utopia framework repository (January 2022, roughly at commit [`03145665`](https://gitlab.com/utopia-project/utopia/-/commit/03145665dc86f223cbd156b98f4c5dc631abc85b)).
There is no changelog going back beyond this point.
