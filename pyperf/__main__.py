#!/usr/bin/env python3

import click
import sys
from .parser import read_file


@click.command()
@click.option(
    "-d", "--directory",
    help="Directory to check files in recursively.",
    type=click.Path(exists=True, readable=True)
)
@click.option(
    "-f", "--file",
    help="Single file to check.",
    type=click.File("r")
)
@click.version_option(version="0.0.1")
def check(*args, **kwargs):
    """Check the requested files."""

    check_file = kwargs.get("file") is not None
    check_dir = kwargs.get("directory") is not None
    if not check_dir and not check_file:
        print("Error: nothing to check! Use pyperf --help for details.")
        sys.exit(1)
    issues = read_file(kwargs.get("file"))
    click.clear()
    if issues is not None and len(issues) > 0:
        click.secho(
            f"Issues found ({kwargs.get('file').name}):",
            fg="bright_red",
            bold=True
        )
        for issue in issues:
            click.secho(f"• {issue}", fg="yellow")
    else:
        click.secho("Looks good!", fg="bright_green")


check()
