"""Various utilities used within the CLI definition and for handling click"""

import click


class Echo:
    """Adds some reusable configurations for styled click.echo calls"""

    @staticmethod
    def success(message: str, *, fg="green", bold=True, **style):
        """An echo that communicates a success"""
        click.secho(message, fg=fg, bold=bold, **style)

    @staticmethod
    def failure(
        message: str,
        *,
        error: Exception = None,
        fg="red",
        bold=True,
        **style,
    ):
        """An echo that can be used to communicate a failure, optionally
        parsing the exception as well.
        """
        click.secho(message, fg=fg, bold=bold, **style)
        if not error:
            return

        click.secho(
            f"{type(error).__name__}: {error}", fg=fg, bold=False, **style
        )

    @staticmethod
    def progress(message: str, *, fg="yellow", bold=True, **style):
        """An echo that communicates some progress"""
        click.secho(message, fg=fg, bold=bold, **style)

    @staticmethod
    def info(message: str, *, dim=True, **style):
        """An echo that communicates some information"""
        click.secho(message, dim=dim, **style)
