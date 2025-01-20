[![utopya logo](doc/_static/img/logo_green.svg)][utopya-repo]

The `utopya` package provides a simulation management and evaluation framework with the following features:

- **Run model simulations** in parallel and on cluster architectures:
    - Conveniently perform parameter sweeps of arbitrary parameters with the help of the [paramspace][paramspace] package.
- A **powerful CLI** to run and evaluate models, including interactive plotting
- Integrates the [dantro][dantro] **data processing pipeline**:
    - Loads data into a hierarchical data tree, supplying a uniform interface.
    - Gives access to a configuration-based **data transformation framework**, separating data preprocessing from visualization for increased generality.
    - Easy extensibility of plot creators via model-specific plot implementations.
- A **versatile configuration interface** for both simulation and evaluation:
    - Assembling multi-level model configurations, including several default levels.
    - Assembling plot configurations with multiple inheritance, reducing redundant definitions.
- The `utopya_backend` package, which assists in implementing models.
- Registration and management of models, projects, and frameworks.
- Managing data output directories.
- Tools to simplify implementation of model tests and working without a CLI.
- ... and more

`utopya` evolved as part of the [Utopia Project][Utopia-Project] and provides the frontend of the [Utopia modelling framework][Utopia].
Having been outsourced from that project, it can be used with arbitrary model implementations and with a very low barrier for entry: in the simplest case, only the path to an executable is required to run simulations.
With more compliance to the utopya interface, more features become available.

The `utopya` package is **open source software** released under the [LGPLv3+][LGPL] license; see [below](#license-copyright).

[[_TOC_]]


<!-- start: installation -->

# Installation
To install utopya, first enter the virtual environment of your choice.
The utopya package is available on [PyPI][utopya-pypi]:

```bash
pip install utopya
```

This will install `utopya`, the `utopya_backend` and the utopya CLI, pulling in all requirements.
You should now be able to invoke the utopya CLI:

```bash
utopya --help
```

*Note:* utopya does not specify minimum versions for its requirements; but it is always tested using the latest versions of its dependencies (for Python 3.9 to 3.13).
In case you run into problems, consider upgrading the involved packages using `pip install --upgrade`.

## Optional Dependencies
To include all optional dependencies in the installation (e.g. for plotting networks), use the following command:

```bash
pip install utopya[opt]
```

This may require that you install the following packages first:
* [graphviz][graphviz]
    * See [the PyGraphviz docs](https://pygraphviz.github.io/documentation/stable/install.html) for further instructions.

<!-- end: installation -->


# Getting started
* For a simple example, see the [demo project](demo/).
* For a larger example of how utopya can be used, have a look at [Utopia][Utopia].
* For more information, refer to the [utopya documentation](https://utopya.readthedocs.io/).




# License & Copyright

The `utopya` package is **open source software** released under the [LGPLv3+][LGPL] license.

## Copyright Notice

    utopya
    Copyright (C) 2018 – 2025  utopya developers

    The term "utopya developers" refers to all direct contributors to this
    software package. A full list of copyright holders and information about
    individual contributions can be retrieved from the version-controlled
    development history of this software package.

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Lesser General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.

A copy of the [GNU General Public License Version 3][GPL], and the [GNU Lesser General Public License Version 3][LGPL] extending it, is distributed with the source code of this program.

## Copyright Holders

The copyright holders of the utopya software package are collectively referred to as "utopya developers" in the respective copyright notices.

* Narek Baghumian
* Lorenzo Biasi
* Thomas Gaskin (@tgaskin)
* Benjamin Herdeanu (@herdeanu)
* Fabian Krautgasser
* Daniel Lake
* Hendrik Leusmann
* Harald Mack (@mackharald89)
* Lukas Riedel (@peanutfun)
* Soeren Rubner (@Nere0s)
* Yunus Sevinchan (@blsqr, *maintainer*)
* Lukas Siebert
* Jeremias Traub (@jeremiastraub)
* Julian Weninger (@JulianWeninger)
* Josephine Westermann

<!-- start: links -->

[GPL]: https://www.gnu.org/licenses/gpl-3.0.en.html
[LGPL]: https://www.gnu.org/licenses/lgpl-3.0.en.html
[utopya-repo]: https://gitlab.com/utopia-project/utopya
[utopya-pypi]: https://pypi.org/project/utopya/
[Utopia]: https://gitlab.com/utopia-project/utopia
[dantro]: https://gitlab.com/utopia-project/dantro
[paramspace]: https://gitlab.com/blsqr/paramspace
[Utopia-Project]: https://utopia-project.org/

[graphviz]: https://graphviz.org
