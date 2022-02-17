"""Various utilities used within the CLI definition and for handling click"""

import click


class Echo:
    """Adds some standardized styled ``click.echo`` calls"""

    @staticmethod
    def remark(message: str, *, fg=246, **style):
        """An echo that communicates some low-level information"""
        click.secho(message, fg=fg, **style)

    @staticmethod
    def note(message: str, *, fg="cyan", **style):
        """An echo that communicates some low-level information"""
        click.secho(message, fg=fg, **style)

    @staticmethod
    def info(message: str, **style):
        """An echo that communicates some information"""
        click.secho(message, **style)

    @staticmethod
    def progress(message: str, *, fg="green", **style):
        """An echo that communicates some progress"""
        click.secho(message, fg=fg, **style)

    @staticmethod
    def caution(message: str, *, fg=202, **style):
        """An echo that communicates a cautioning message"""
        click.secho(message, fg=fg, **style)

    @staticmethod
    def hilight(message: str, *, fg="yellow", bold=True, **style):
        """An echo that highlights a certain"""
        click.secho(message, fg=fg, bold=bold, **style)

    @staticmethod
    def success(message: str, *, fg="green", bold=True, **style):
        """An echo that communicates a success"""
        click.secho(message, fg=fg, bold=bold, **style)

    @staticmethod
    def warning(message: str, *, fg=202, bold=True, **style):
        """An echo that communicates a warning"""
        click.secho(message, fg=fg, bold=bold, **style)

    @staticmethod
    def error(
        message: str,
        *,
        error: Exception = None,
        fg="red",
        bold=True,
        **style,
    ):
        """An echo that can be used to communicate an error, optionally
        parsing the exception's error message as well.
        """
        click.secho(message, fg=fg, bold=bold, **style)
        if not error:
            return

        click.secho(
            f"{type(error).__name__}: {error}", fg=fg, bold=False, **style
        )
