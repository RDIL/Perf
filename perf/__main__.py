#!/usr/bin/env python3

import click
import sys
import area4
from .parser import read_file
from os import listdir
from os.path import isfile
from .util import note_errors_present, note_errors


@click.command()
@click.option(
    "-d",
    "--directory",
    help="Directory to check files in recursively.",
    type=click.Path(exists=True, readable=True),
)
@click.option(
    "-f", "--file", help="Single file to check.", type=click.File("r")
)
@click.version_option(version="0.1.0")
def check(*args, **kwargs):
    """Check the requested files."""

    check_file = kwargs.get("file") is not None
    check_dir = kwargs.get("directory") is not None

    if not check_dir and not check_file:
        click.secho(
            "Error: nothing to check! Use `python3 -m perf --help`", fg="red"
        )
        sys.exit(1)

    click.clear()

    divider = area4.make_div("=", start=">", end="<", length=10)

    click.secho(divider, fg="blue")
    click.secho("   Perf   ", bold=True)
    click.secho(divider, fg="blue")
    click.echo()

    if check_file:
        issues = read_file(kwargs.get("file"))

        if issues is not None and len(issues) > 0:
            note_errors_present(kwargs.get("file").name)
            note_errors(issues)
            sys.exit(1)

    else:
        has_problems = False
        for file in listdir(kwargs.get("directory")):
            if isfile(file):
                issues = read_file(open(file, "r"))

                if issues is not None and len(issues) > 0:
                    note_errors_present(file)
                    note_errors(issues)
                    has_problems = True
        if has_problems:
            sys.exit(1)

    click.secho("Everything looks good!", fg="bright_green")


check()
