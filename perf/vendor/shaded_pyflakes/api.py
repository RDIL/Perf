import ast
import re
import sys

from . import checker, messages


def check(codeString, file_name):
    # First, compile into an AST and handle syntax errors.
    try:
        tree = ast.parse(codeString)
    except SyntaxError:
        value = sys.exc_info()[1]

        (lineno, offset, text) = value.lineno, value.offset, value.text

        if checker.PYPY:
            if text is None:
                lines = codeString.splitlines()
                if len(lines) >= lineno:
                    text = lines[lineno - 1]
                    if isinstance(text, bytes):
                        try:
                            text = text.decode("ascii")
                        except UnicodeDecodeError:
                            text = None
            offset -= 1

        # If there's an encoding problem with the file, the text is None.
        if text is None:
            # Avoid using msg, since for the only known case, it contains a
            # bogus message that claims the encoding the file declared was
            # unknown.
            return [messages.SourceDecodeError(0)]
        else:
            return [messages.ParseSyntaxError(0)]
    except Exception:
        return [messages.SourceDecodeError(0)]

    # Okay, it's syntactically valid, now check it.
    file_tokens = checker.make_tokens(codeString)
    w = checker.Checker(
        tree, file_tokens=file_tokens, is__init__=file_name == "__init__.py"
    )
    w.messages.sort(key=lambda m: m.lineno)
    return w.messages


def isPythonFile(filename):
    if filename.endswith(".py"):
        return True

    # Avoid obvious Emacs backups
    if filename.endswith("~"):
        return False

    max_bytes = 128

    try:
        with open(filename, "rb") as f:
            text = f.read(max_bytes)
            if not text:
                return False
    except IOError:
        return False

    return re.compile(br"^#!.*\bpython([23](\.\d+)?|w)?[dmu]?\s").match(text)
