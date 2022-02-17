"""Various utilities used within the CLI definition and for handling click"""

import click


def _parse_msg(msg: str, args) -> str:
    if args:
        return msg % args
    return msg


class Echo:
    """Adds some standardized styled ``click.echo`` calls"""

    @staticmethod
    def trace(msg: str, *args, dim=True, **style):
        """An echo that communicates some debug-level information"""
        click.secho(_parse_msg(msg, args), dim=dim, **style)

    @staticmethod
    def debug(msg: str, *args, dim=True, **style):
        """An echo that communicates some debug-level information"""
        click.secho(_parse_msg(msg, args), dim=dim, **style)

    @staticmethod
    def remark(msg: str, *args, fg=246, **style):
        """An echo that communicates some low-level information"""
        click.secho(_parse_msg(msg, args), fg=fg, **style)

    @staticmethod
    def note(msg: str, *args, fg="cyan", **style):
        """An echo that communicates some low-level information"""
        click.secho(_parse_msg(msg, args), fg=fg, **style)

    @staticmethod
    def info(msg: str, *args, **style):
        """An echo that communicates some information"""
        click.secho(_parse_msg(msg, args), **style)

    @staticmethod
    def progress(msg: str, *args, fg="green", **style):
        """An echo that communicates some progress"""
        click.secho(_parse_msg(msg, args), fg=fg, **style)

    @staticmethod
    def caution(msg: str, *args, fg=202, **style):
        """An echo that communicates a cautioning message"""
        click.secho(_parse_msg(msg, args), fg=fg, **style)

    @staticmethod
    def hilight(msg: str, *args, fg="yellow", bold=True, **style):
        """An echo that highlights a certain"""
        click.secho(_parse_msg(msg, args), fg=fg, bold=bold, **style)

    @staticmethod
    def success(msg: str, *args, fg="green", bold=True, **style):
        """An echo that communicates a success"""
        click.secho(_parse_msg(msg, args), fg=fg, bold=bold, **style)

    @staticmethod
    def warning(msg: str, *args, fg=202, bold=True, **style):
        """An echo that communicates a warning"""
        click.secho(_parse_msg(msg, args), fg=fg, bold=bold, **style)

    @staticmethod
    def error(
        msg: str,
        *args,
        error: Exception = None,
        fg="red",
        bold=True,
        **style,
    ):
        """An echo that can be used to communicate an error, optionally
        parsing the exception's error msg as well.
        """
        click.secho(_parse_msg(msg, args), fg=fg, bold=bold, **style)
        if not error:
            return

        click.secho(
            f"{type(error).__name__}: {error}", fg=fg, bold=False, **style
        )
