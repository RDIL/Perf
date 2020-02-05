import re
import functools
import os
import json


@functools.lru_cache(maxsize=None)
def load_regex():
    """Loads the regex strings from the file into a dict."""

    return json.loads(
        open(
            os.path.abspath(os.path.dirname(__file__)) + "/regex.json", "r"
        ).read()
    )


def read_file(file):
    """Reads a file and finds issues."""

    issues = []
    lines = file.readlines()
    # individual line processing
    import_count = 0
    for i, x in enumerate(lines):
        line = lines[i]

        if is_import(line):
            import_count += 1

        if using_string_concatenation(line):
            issues.append(
                error_template(
                    "is using string joining (can get very slow)", i
                )
            )

        if "global " in line:
            issues.append(error_template("is loading globals (slow)", i))

        if using_whiletrue(line):
            issues.append(
                error_template(
                    "is using while True (faster alternative available)", i
                )
            )

    if import_count >= 15:
        issues.append(
            error_template("has more then 15 imports (adds overhead)")
        )

    # multiline block processing
    lineblock = "\n".join(lines)

    if using_slow_overlap_checking(lineblock):
        issues.append(
            error_template("Looks to be using overlap checking in a slow way")
        )

    return issues


def using_string_concatenation(line):
    """Returns if the line is using the plusEquals pattern."""

    return re.match(re.compile(load_regex()["plusEquals"]), line)


def using_slow_overlap_checking(lines):
    """Checks if the file is using the overlapChecking pattern."""

    matches = re.finditer(re.compile(load_regex()["overlapChecking"]), lines)
    return matches


def using_whiletrue(line):
    """Check if the file uses the whileTrue pattern."""

    return re.match(re.compile(load_regex()["whileTrue"]), line)


def is_import(line):
    """Returns if the line is an import."""

    return "import " in line or "__import__" in line


def error_template(issue, *args):
    """Formats an error reported by the tool."""

    if args is not None:
        return issue.capitalize()
    return str(args).join(["Line ", " " + issue])
