class Message:
    message = ""
    message_args = ()

    def __init__(self, loc):
        self.lineno = loc.lineno

    def __str__(self):
        return self.message % self.message_args


class UnusedImport(Message):
    message = "%r imported but unused"

    def __init__(self, loc, name):
        Message.__init__(self, loc)
        self.message_args = (name,)


class RedefinedWhileUnused(Message):
    message = "redefinition of unused %r from line %r"

    def __init__(self, filename, loc, name, orig_loc):
        Message.__init__(self, filename, loc)
        self.message_args = (name, orig_loc.lineno)


class RedefinedInListComp(Message):
    message = "list comprehension redefines %r from line %r"

    def __init__(self, filename, loc, name, orig_loc):
        Message.__init__(self, filename, loc)
        self.message_args = (name, orig_loc.lineno)


class ImportShadowedByLoopVar(Message):
    message = "import %r from line %r shadowed by loop variable"

    def __init__(self, filename, loc, name, orig_loc):
        Message.__init__(self, filename, loc)
        self.message_args = (name, orig_loc.lineno)


class ImportStarNotPermitted(Message):
    message = "'from %s import *' only allowed at module level"

    def __init__(self, filename, loc, modname):
        Message.__init__(self, filename, loc)
        self.message_args = (modname,)


class ImportStarUsed(Message):
    message = "'from %s import *' used; unable to detect undefined names"

    def __init__(self, filename, loc, modname):
        Message.__init__(self, filename, loc)
        self.message_args = (modname,)


class ImportStarUsage(Message):
    message = "%r may be undefined, or defined from star imports: %s"

    def __init__(self, filename, loc, name, from_list):
        Message.__init__(self, filename, loc)
        self.message_args = (name, from_list)


class UndefinedName(Message):
    message = "undefined name %r"

    def __init__(self, filename, loc, name):
        Message.__init__(self, filename, loc)
        self.message_args = (name,)


class UndefinedExport(Message):
    message = "undefined name %r in __all__"

    def __init__(self, filename, loc, name):
        Message.__init__(self, filename, loc)
        self.message_args = (name,)


class UndefinedLocal(Message):
    message = "local variable %r {0} referenced before assignment"

    default = "defined in enclosing scope on line %r"
    builtin = "defined as a builtin"

    def __init__(self, filename, loc, name, orig_loc):
        Message.__init__(self, filename, loc)
        if orig_loc is None:
            self.message = self.message.format(self.builtin)
            self.message_args = name
        else:
            self.message = self.message.format(self.default)
            self.message_args = (name, orig_loc.lineno)


class DuplicateArgument(Message):
    message = "duplicate argument %r in function definition"

    def __init__(self, filename, loc, name):
        Message.__init__(self, filename, loc)
        self.message_args = (name,)


class MultiValueRepeatedKeyLiteral(Message):
    message = "dictionary key %r repeated with different values"

    def __init__(self, filename, loc, key):
        Message.__init__(self, filename, loc)
        self.message_args = (key,)


class MultiValueRepeatedKeyVariable(Message):
    message = "dictionary key variable %s repeated with different values"

    def __init__(self, filename, loc, key):
        Message.__init__(self, filename, loc)
        self.message_args = (key,)


class LateFutureImport(Message):
    message = "from __future__ imports must occur at the beginning of the file"

    def __init__(self, filename, loc, names):
        Message.__init__(self, filename, loc)
        self.message_args = ()


class UnusedVariable(Message):
    message = "local variable %r is assigned to but never used"

    def __init__(self, filename, loc, names):
        Message.__init__(self, filename, loc)
        self.message_args = (names,)


class ReturnWithArgsInsideGenerator(Message):
    message = "'return' with argument inside generator"


class DefaultExceptNotLast(Message):
    message = "default 'except:' must be last"


class TwoStarredExpressions(Message):
    message = "two starred expressions in assignment"


class TooManyExpressionsInStarredAssignment(Message):
    message = "too many expressions in star-unpacking assignment"


class AssertTuple(Message):
    message = "assertion is always true, perhaps remove parentheses?"


class RaiseNotImplemented(Message):
    message = "'raise NotImplemented' should be 'raise NotImplementedError'"


class InvalidPrintSyntax(Message):
    message = "use of >> is invalid with print function"


class FStringMissingPlaceholders(Message):
    message = "f-string is missing placeholders"


class StringDotFormatExtraPositionalArguments(Message):
    message = "'...'.format(...) has unused arguments at position(s): %s"

    def __init__(self, filename, loc, extra_positions):
        Message.__init__(self, filename, loc)
        self.message_args = (extra_positions,)


class StringDotFormatExtraNamedArguments(Message):
    message = "'...'.format(...) has unused named argument(s): %s"

    def __init__(self, filename, loc, extra_keywords):
        Message.__init__(self, filename, loc)
        self.message_args = (extra_keywords,)


class StringDotFormatMixingAutomatic(Message):
    message = "'...'.format(...) mixes automatic and manual numbering"


class StringDotFormatInvalidFormat(Message):
    message = "'...'.format(...) has invalid format string: %s"

    def __init__(self, filename, loc, error):
        Message.__init__(self, filename, loc)
        self.message_args = (error,)


class PercentFormatExtraNamedArguments(Message):
    message = "'...' %% ... has unused named argument(s): %s"

    def __init__(self, filename, loc, extra_keywords):
        Message.__init__(self, filename, loc)
        self.message_args = (extra_keywords,)


class PercentFormatMissingArgument(Message):
    message = "'...' %% ... is missing argument(s) for placeholder(s): %s"

    def __init__(self, filename, loc, missing_arguments):
        Message.__init__(self, filename, loc)
        self.message_args = (missing_arguments,)


class ParseSyntaxError(Message):
    message = "Syntax error, stopping parsing early"


class SourceDecodeError(Message):
    message = "Error decoding source"
