# `utopya`

This repo hosts the `utopya` Python package, which provides simulation management and evaluation for [Utopia] and beyond.

[[_TOC_]]

---

## About `utopya`
`utopya` is a Python package that provides the frontend for the [Utopia] simulation framework but can also be used with other software.
It aims to provide a simulation management and evaluation framework with the following feature set:

- Model configuration with several update levels
- A powerful CLI to run and evaluate models
- Executing model simulations in parallel and on cluster architectures
- Managing data output directories
- Interfacing with the [dantro] data processing pipeline


## Installation
To install utopya, enter the virtual environment of your choice and call:

```
pip install git+https://gitlab.com/utopia-project/utopya.git
```

To install from a certain branch, append `@<branch-name>` to the end of the command.

⚠️ Note that utopya is **not** on PyPI (yet)!
The package of the same name is a scam that we are hoping to get removed soon.

The above command will install utopya and the utopya CLI, pulling in all requirements.
You should now be able to invoke the utopya CLI:

```
utopya --help
```

## Basic Usage
🚧

See the [demo project](demo/) for an implementation example.




## License & Copyright
### Copyright Notice

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

A copy of the [GNU General Public License Version 3][GPL], and the
[GNU Lesser General Public License Version 3][LGPL] extending it, is distributed with
the source code of this program.

### Copyright Holders

The copyright holders of the utopya software package are collectively referred
to as "utopya developers" in the respective copyright notices.

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
[Utopia]: https://utopia-project.org/
[dantro]: https://dantro.readthedocs.io/
