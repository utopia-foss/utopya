[![utopya logo](doc/_static/img/logo_green.svg)][utopya-repo]

The `utopya` package provides a simulation management and evaluation framework with the following feature set:

- **Run model simulations** in parallel and on cluster architectures
    - Conveniently perform parameter sweeps of arbitrary parameters with the help of the [paramspace][paramspace] package.
- A **powerful CLI** to run and evaluate models, including interactive plotting
- Integrates the [dantro][dantro] **data processing pipeline**:
    - Loads data into a hierarchical data tree, supplying a uniform interface
    - Gives access to a configuration-based **data transformation framework**, separating data preprocessing from visualization for increased generality
    - Easy extensibility of plot creators via model-specific plot implementations
- A **versatile configuration interface** for both simulation and evaluation:
    - Assembling multi-level model configurations, including several default levels
    - Assembling plot configurations with multiple inheritance, reducing redundant definitions
- Model, project, and framework registration and handling
- Managing data output directories
- Tools to simplify model test implementations or working without a CLI
- ... and more

The `utopya` package evolved as part of the [Utopia Project][Utopia-Project] and provides the frontend of the [Utopia modelling framework][Utopia].
Having been outsourced from that project, it can be used with arbitrary model implementations with a very low barrier for entry: in the simplest case, only the path to an executable is required to run simulations.
With more compliance to the utopya interface, more features become available.

The `utopya` package is **open source software** released under the [LGPLv3+][LGPL] license; see [below](#license-copyright).

[[_TOC_]]




# Installation
To install utopya, first enter the virtual environment of your choice.
The utopya package is available on [PyPI][utopya-pypi]:

```
pip install --pre utopya
```

Alternatively, use the following command to install from a certain branch:

```
pip install git+https://gitlab.com/utopia-project/utopya.git@<branch-name>
```

The above commands will install utopya and the utopya CLI, pulling in all requirements.
You should now be able to invoke the utopya CLI:

```
utopya --help
```

# Basic Usage
🚧

See the [demo project](demo/) for an implementation example.




# License & Copyright

The `utopya` package is **open source software** released under the [LGPLv3+][LGPL] license.

## Copyright Notice

    utopya
    Copyright (C) 2018 – 2022  utopya developers

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

[GPL]: https://www.gnu.org/licenses/gpl-3.0.en.html
[LGPL]: https://www.gnu.org/licenses/lgpl-3.0.en.html
[utopya-repo]: https://gitlab.com/utopia-project/utopya
[utopya-pypi]: https://pypi.org/project/utopya/
[Utopia]: https://gitlab.org/utopia-project/utopia
[dantro]: https://gitlab.org/utopia-project/dantro
[paramspace]: https://gitlab.com/blsqr/paramspace
[Utopia-Project]: https://utopia-project.org/
