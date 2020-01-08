import click


@click.command()
@click.option(
    "-f", "--files",
    help="File(s) to check.",
    type=click.Path(exists=True, readable=True),
    required=True
)
def check(files):
    """Check the passed files."""
    print(files)


if __name__ == '__main__':
    check()
