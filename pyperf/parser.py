import re
import functools
import os
import json


@functools.lru_cache(maxsize=None)
def load_regex():
    return json.loads(
        open(
            os.path.abspath(os.path.dirname(__file__)) + "regex.json",
            "r"
        ).read()
    )


def read_file(file):
    """Reads a file and finds issues."""
    issues = []
    lines = file.readlines()
    # individual line processing
    for i, x in enumerate(lines):
        if using_string_concatenation(lines[i]):
            issues.append(
                error_template(
                    i, "is using string joining (can get very slow)"
                )
            )
        if "global " in lines[i]:
            issues.append(error_template(i, "is loading globals (slow)"))
        if using_whiletrue(lines[i]):
            issues.append(
                error_template(
                    i, "is using while True (faster alternative available)"
                )
            )

    # multiline block processing
    lineblock = "\n".join(lines)

    if using_slow_overlap_checking(lineblock):
        issues.append(
            error_template(
                "unknown", "looks to be using overlap checking in a slow way"
            )
        )

    return issues


def using_string_concatenation(line):
    return re.match(re.compile(load_regex()["plusEquals"]), line)


def using_slow_overlap_checking(lines):
    matches = re.finditer(re.compile(load_regex()["overlapChecking"]), lines)
    return matches


def using_whiletrue(line):
    return re.match(re.compile(load_regex()["whileTrue"]), line)


def error_template(lineno, issue):
    return str(
        lineno
    ).join([
        "Line ",
        f" {issue}"
    ])
