"""Sets up the utopya package, test dependencies, and command line scripts"""

from setuptools import find_packages, setup

# Dependency lists
INSTALL_DEPS = [
    "numpy>=1.21",
    "scipy>=1.7.3",
    "matplotlib>=3.3",
    "seaborn>=0.11.2",
    "ruamel.yaml>=0.16.5",
    "coloredlogs>=15.0",
    "colorama>=0.4.4",
    "click>=8.0",
    "pydantic>=1.9",
    #
    # related to utopya:
    "paramspace>=2.5.9",
    "dantro>=0.17.2",
]
# NOTE When changing any of the dependencies, make sure to update the table of
#      dependencies in README.md.
#      When adding a NEW dependency, make sure to denote it in the isort
#      configuration, see pyproject.toml.

# Dependencies for running tests and general development of dantro
TEST_DEPS = [
    "pytest>=6.2",
    "pytest-cov>=2.10",
    "pre-commit>=2.16",
]

# Dependencies for building the dantro documentation
DOC_DEPS = [
    "sphinx>=4",
    "sphinx-book-theme",
    "ipython>=7.0",
]


DESCRIPTION = "A simulation management and evaluation framework"
LONG_DESCRIPTION = """
``utopya``: A simulation management and evaluation framework
============================================================

The ``utopya`` package aims to provide a simulation management and evaluation
framework with the following feature set:

- Provide model configuration with several update levels
- Project and framework handling
- A powerful CLI to run and evaluate models
- Executing model simulations in parallel and on cluster architectures
- Managing data output directories
- Interfacing with the `dantro <https://gitlab.com/utopia-project/dantro>`_
  data processing pipeline

It evolved as part of the `Utopia Project <https://utopia-project.org>`_ and
provides the frontend of the `Utopia modelling framework <https://gitlab.com/utopia-project/utopia>`_.
Having been outsourced from that project, it can be used with arbitrary model
implementations with a very low barrier for entry: in the simplest case, only
only the path to an executable is required to run simulations.
With more compliance to the utopya interface, more features become available.

Visit the `project website <https://gitlab.com/utopia-project/utopya>`_ for more information and documentation.
"""
# TODO Mention docs


# .............................................................................


def find_version(*file_paths) -> str:
    """Tries to extract a version from the given path sequence"""
    import codecs
    import os
    import re

    def read(*parts):
        """Reads a file from the given path sequence, relative to this file"""
        here = os.path.abspath(os.path.dirname(__file__))
        with codecs.open(os.path.join(here, *parts), "r") as fp:
            return fp.read()

    # Read the file and match the __version__ string
    file = read(*file_paths)
    match = re.search(r"^__version__\s?=\s?['\"]([^'\"]*)['\"]", file, re.M)
    if match:
        return match.group(1)
    raise RuntimeError("Unable to find version string in " + str(file_paths))


# .............................................................................


setup(
    name="utopya",
    #
    # Package information
    version=find_version("utopya", "__init__.py"),
    #
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    url="https://gitlab.com/utopia-project/utopya",
    author="utopya developers",
    author_email=(
        "Benjamin Herdeanu <Benjamin.Herdeanu@iup.uni-heidelberg.de>, "
        "Yunus Sevinchan <Yunus.Sevinchan@iup.uni-heidelberg.de>"
    ),
    classifiers=[
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)",
        "Topic :: Utilities",
    ],
    #
    # Package content and dependencies
    packages=find_packages(exclude=("demo", "tests")),
    package_data=dict(utopya=["cfg/*.yml"]),
    install_requires=INSTALL_DEPS,
    extras_require=dict(
        test=TEST_DEPS,
        doc=DOC_DEPS,
        dev=TEST_DEPS + DOC_DEPS,
    ),
    #
    # Command line scripts
    entry_points={
        "console_scripts": [
            "utopya = utopya_cli.cli:cli",
        ],
    },
)
