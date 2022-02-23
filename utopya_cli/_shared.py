"""Defines arguments that are shared across various parts of the CLI"""

import click


def add_options(options):
    def _add_options(func):
        for option in reversed(options):
            func = option(func)
        return func

    return _add_options


# -----------------------------------------------------------------------------

OPTIONS = dict()

# -- Data loading options
OPTIONS["load"] = (
    click.option(
        "-P",
        "--load-parallel",
        flag_value=True,
        default=None,
        help=("If given, will force loading data in parallel."),
    ),
    click.option(
        "--use-data-tree-cache",
        "--tc",
        flag_value=True,
        default=None,
        help=(
            "If set, uses tree file caching: If no cache file exists, creates "
            "one after loading all data; if a tree file already exists, uses "
            "that to restore the data tree. This may bring a speed-up if the "
            "creation of the data tree takes a long time."
        ),
    ),
    click.option(
        "--show-data-tree",
        type=click.Choice(("full", "condensed", "none")),
        default="condensed",
        show_default=True,
        help="Controls which kind of data tree should be shown after loading.",
    ),
    click.option(
        "--cluster-mode",
        flag_value=True,
        default=None,
        help="Enables cluster mode.",
    ),
)


# -- Evaluation options
OPTIONS["eval"] = (
    click.option(
        "--plots-cfg",
        default=None,
        type=click.Path(exists=True, dir_okay=False, resolve_path=True),
        help=(
            "If given, uses the plots configuration file found at this path "
            "instead of the defaults for the model."
        ),
    ),
    click.option(
        "-u",
        "--update-plots-cfg",
        multiple=True,
        help=(
            "Sets entries in the selected plots config. "
            "Example: -u my_plot.some_param=42 sets the 'some_param' entry "
            "in the plot configuration named 'my_plot'. "
            "Repeat the -u option to set multiple values."
        ),
    ),
    click.option(
        "--plot-only",
        "--po",
        "plot_only",
        multiple=True,
        help=(
            "If given, will plot only those entries of the plot configuration "
            "that match the names given here. This can also be used to "
            "activate plots that are disabled in the specified plot "
            "configuration. Note that simple name globbing is supported, but "
            "the argument needs to be put into quotes to not conflict with "
            "the globbing done by the shell. "
            "Repeat the --po option to denote multiple plot_only arguments."
        ),
    ),
    click.option(
        "-i",
        "--interactive",
        flag_value=True,
        help=(
            "If set, the CLI will not exit after plotting finished, but allow "
            "to continue plotting in an interactive session. "
            "This option is useful for creating multiple plots in an "
            "iterative fashion, especially if data loading time is large. "
            "Note that all Multiverse-related configuration options can not "
            "be changed during the session and have to be set beforehand."
        ),
    ),
    click.option(
        "-R",
        "--reveal-output",
        flag_value=True,
        help="If set, opens the output directory after plotting finished.",
    ),
)
