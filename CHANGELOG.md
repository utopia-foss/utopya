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
- !4 adds a validated project registry


## v0.8.8
This is the version specification of `utopya` at the time it was outsourced from the Utopia framework repository (January 2022, roughly at commit [`03145665`](https://ts-gitlab.iup.uni-heidelberg.de/utopia/utopia/-/commit/03145665dc86f223cbd156b98f4c5dc631abc85b)).
There is no changelog going back beyond this point.
