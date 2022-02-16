"""Test module for the `utopya_cli` package"""

from click.testing import CliRunner

from utopya_cli import cli

runner = CliRunner()
invoke_cli = lambda *a, **kw: runner.invoke(cli, *a, **kw)
