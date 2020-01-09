import click
import sys


def note_errors_present(file):
    click.secho(
        f"Issues found ({file}):",
        fg="bright_red",
        bold=True
    )


def note_errors(issues):
    if issues is not None and len(issues) > 0:
        for issue in issues:
            click.secho(f"• {issue}", fg="yellow")
        sys.exit(1)
