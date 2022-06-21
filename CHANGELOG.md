# Changelog

`utopya` aims to adhere to [semantic versioning](https://semver.org/).


## v1.0.0 *(WIP)*
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
- !4 and !6 add a validated project registry, which keeps track of utopya projects (which in turn contain models) and frameworks: two abstraction levels that play a role in determining the configuration hierarchy.
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
- !8 improves the package API documentation and implements intersphinx for cross-referencing to other packages.
- !9 adapts the package structure to the reworked dantro >= v0.18 interface
    - This pertains mostly to the plotting framework. Due to utopya wrapping many parts of that interface, there are few backwards-*incompatible* changes.
    - However, notice the [deprecations](https://gitlab.com/utopia-project/dantro/-/blob/master/CHANGELOG.md#v0180) introduced by dantro v0.18.

### Internal
- !10 outsources `utopya._import_tools` to `dantro._import_tools`


## v0.8.8
This is the version specification of `utopya` at the time it was outsourced from the Utopia framework repository (January 2022, roughly at commit [`03145665`](https://gitlab.com/utopia-project/utopia/-/commit/03145665dc86f223cbd156b98f4c5dc631abc85b)).
There is no changelog going back beyond this point.
