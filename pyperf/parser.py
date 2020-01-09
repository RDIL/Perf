import re
from .regex_db import combine_strings


def read_file(file):
    """Reads a file and finds issues."""
    issues = []
    lines = file.readlines()
    for i, x in enumerate(lines):
        if using_string_concatenation(lines[i]):
            issues.append(
                error_template(
                    i, "is using string joining (can get very slow)"
                )
            )
        if "global " in lines[i]:
            issues.append(error_template(i, "is loading globals (slow)"))

    return issues


def using_string_concatenation(line):
    return re.match(combine_strings, line)


def error_template(lineno, issue):
    return str(
        lineno
    ).join([
        "Line ",
        f" {issue}"
    ])
