import click


def note_errors_present(file):
    click.secho(f"Issues found ({file}):", fg="bright_red", bold=True)


def note_errors(issues):
    for issue in issues:
        click.secho(f"• {issue}", fg="yellow")
