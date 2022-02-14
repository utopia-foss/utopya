"""Various utilities used within the CLI definition and for handling click"""

import click


class Echo:
    """Adds some reusable configurations for styled click.echo calls"""

    @staticmethod
    def success(message: str, *, fg="green", bold=True, **style_kwargs):
        """An echo that communicates a success"""
        click.secho(message, fg=fg, bold=bold, **style_kwargs)

    @staticmethod
    def failure(
        message: str,
        *,
        error: Exception = None,
        fg="red",
        bold=True,
        **style_kwargs,
    ):
        """An echo in case of a failure"""
        click.secho(message, fg=fg, bold=bold, **style_kwargs)
        if error:
            click.secho(error, fg=fg, bold=False, **style_kwargs)

    @staticmethod
    def progress(message: str, *, fg="yellow", bold=True, **style_kwargs):
        """An echo that communicates some progress"""
        click.secho(message, fg=fg, bold=bold, **style_kwargs)

    @staticmethod
    def info(message: str, *, dim=True, **style_kwargs):
        """An echo that communicates some information"""
        click.secho(message, dim=dim, **style_kwargs)
