import re
from .regex_db import combine_strings


def read_file(file):
    """Reads a file and finds issues."""
    issues = []
    lines = file.readlines()
    for i, x in enumerate(lines):
        if using_string_concatenation(lines[i]):
            issues.append(
                str(i).join(
                    ["line ", " is using slow string joining (+=)"]
                )
            )

    return issues


def using_string_concatenation(line):
    return re.match(combine_strings, line)
