import ast
import bisect
import collections
import doctest
import functools
import os
import re
import string
import sys
import tokenize
from . import messages

PY35_PLUS = sys.version_info >= (3, 5)
PY36_PLUS = sys.version_info >= (3, 6)
PY38_PLUS = sys.version_info >= (3, 8)
try:
    sys.pypy_version_info  # type: ignore
    PYPY = True
except AttributeError:
    PYPY = False

builtin_vars = dir(__import__("builtins"))

parse_format_string = string.Formatter().parse


def getNodeType(node_class):
    return node_class.__name__.upper()


def get_raise_argument(node):
    return node.exc


# Silence `pyflakes` from reporting `undefined name 'unicode'` in Python 3.
unicode = str


def getAlternatives(n):
    if isinstance(n, ast.If):
        return [n.body]
    if isinstance(n, ast.Try):
        return [n.body + n.orelse] + [[hdl] for hdl in n.handlers]


if PY35_PLUS:
    FOR_TYPES = (ast.For, ast.AsyncFor)
    LOOP_TYPES = (ast.While, ast.For, ast.AsyncFor)
    FUNCTION_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)
else:
    FOR_TYPES = ast.For  # type: ignore
    LOOP_TYPES = (ast.While, ast.For)  # type: ignore
    FUNCTION_TYPES = ast.FunctionDef  # type: ignore

# https://github.com/python/typed_ast/blob/1.4.0/ast27/Parser/tokenizer.c#L102-L104
TYPE_COMMENT_RE = re.compile(r"^#\s*type:\s*")
# https://github.com/python/typed_ast/blob/1.4.0/ast27/Parser/tokenizer.c#L1408-L1413
ASCII_NON_ALNUM = "".join([chr(i) for i in range(128) if not chr(i).isalnum()])
TYPE_IGNORE_RE = re.compile(
    TYPE_COMMENT_RE.pattern + r"ignore([{}]|$)".format(ASCII_NON_ALNUM)
)
# https://github.com/python/typed_ast/blob/1.4.0/ast27/Grammar/Grammar#L147
TYPE_FUNC_RE = re.compile(r"^(\(.*?\))\s*->\s*(.*)$")


MAPPING_KEY_RE = re.compile(r"\(([^()]*)\)")
CONVERSION_FLAG_RE = re.compile("[#0+ -]*")
WIDTH_RE = re.compile(r"(?:\*|\d*)")
PRECISION_RE = re.compile(r"(?:\.(?:\*|\d*))?")
LENGTH_RE = re.compile("[hlL]?")
# https://docs.python.org/3/library/stdtypes.html#old-string-formatting
VALID_CONVERSIONS = frozenset("diouxXeEfFgGcrsa%")


def _must_match(regex, string, pos):
    match = regex.match(string, pos)
    assert match is not None
    return match


def parse_percent_format(s):
    """Copied from https://github.com/asottile/pyupgrade at v1.20.1"""

    def _parse_inner():
        string_start = 0
        string_end = 0
        in_fmt = False

        i = 0
        while i < len(s):
            if not in_fmt:
                try:
                    i = s.index("%", i)
                except ValueError:  # no more % fields!
                    yield s[string_start:], None
                    return
                else:
                    string_end = i
                    i += 1
                    in_fmt = True
            else:
                key_match = MAPPING_KEY_RE.match(s, i)
                if key_match:
                    key = key_match.group(1)
                    i = key_match.end()
                else:
                    key = None

                conversion_flag_match = _must_match(CONVERSION_FLAG_RE, s, i)
                conversion_flag = conversion_flag_match.group() or None
                i = conversion_flag_match.end()

                width_match = _must_match(WIDTH_RE, s, i)
                width = width_match.group() or None
                i = width_match.end()

                precision_match = _must_match(PRECISION_RE, s, i)
                precision = precision_match.group() or None
                i = precision_match.end()

                # length modifier is ignored
                i = _must_match(LENGTH_RE, s, i).end()

                try:
                    conversion = s[i]
                except IndexError:
                    raise ValueError("end-of-string while parsing format")
                i += 1

                fmt = (key, conversion_flag, width, precision, conversion)
                yield s[string_start:string_end], fmt

                in_fmt = False
                string_start = i

        if in_fmt:
            raise ValueError("end-of-string while parsing format")

    return tuple(_parse_inner())


class _FieldsOrder(dict):
    def _get_fields(self, node_class):
        # handle iter before target, and generators before element
        fields = node_class._fields
        if "iter" in fields:
            key_first = "iter".find
        elif "generators" in fields:
            key_first = "generators".find
        else:
            key_first = "value".find
        return tuple(sorted(fields, key=key_first, reverse=True))

    def __missing__(self, node_class):
        self[node_class] = fields = self._get_fields(node_class)
        return fields


def counter(items):
    results = {}
    for item in items:
        results[item] = results.get(item, 0) + 1
    return results


def iter_child_nodes(node, omit=None, _fields_order=_FieldsOrder()):
    for name in _fields_order[node.__class__]:
        if omit and name in omit:
            continue
        field = getattr(node, name, None)
        if isinstance(field, ast.AST):
            yield field
        elif isinstance(field, list):
            for item in field:
                yield item


def convert_to_value(item):
    if isinstance(item, ast.Str):
        return item.s
    elif hasattr(ast, "Bytes") and isinstance(item, ast.Bytes):
        return item.s
    elif isinstance(item, ast.Tuple):
        return tuple(convert_to_value(i) for i in item.elts)
    elif isinstance(item, ast.Num):
        return item.n
    elif isinstance(item, ast.Name):
        result = VariableKey(item=item)
        constants_lookup = {
            "True": True,
            "False": False,
            "None": None,
        }
        return constants_lookup.get(result.name, result,)
    elif isinstance(item, ast.NameConstant):
        # None, True, False are nameconstants in python3, but names in 2
        return item.value
    else:
        return UnhandledKeyType()


def is_notimplemented_name_node(node):
    return isinstance(node, ast.Name) and getNodeName(node) == "NotImplemented"


class Binding:
    def __init__(self, name, source):
        self.name = name
        self.source = source
        self.used = False

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<%s object %r from line %r at 0x%x>" % (
            self.__class__.__name__,
            self.name,
            self.source.lineno,
            id(self),
        )

    def redefines(self, other):
        return isinstance(other, Definition) and self.name == other.name


class Definition(Binding):
    """A binding that defines a function or a class."""


class Builtin(Definition):
    def __init__(self, name):
        super(Builtin, self).__init__(name, None)

    def __repr__(self):
        return "<%s object %r at 0x%x>" % (
            self.__class__.__name__,
            self.name,
            id(self),
        )


class UnhandledKeyType:
    """A dictionary key of a type that we cannot or do not check for duplicates."""


class VariableKey:
    def __init__(self, item):
        self.name = item.id

    def __eq__(self, compare):
        return (
            compare.__class__ == self.__class__ and compare.name == self.name
        )

    def __hash__(self):
        return hash(self.name)


class Importation(Definition):
    def __init__(self, name, source, full_name=None):
        self.fullName = full_name or name
        self.redefined = []
        super(Importation, self).__init__(name, source)

    def redefines(self, other):
        if isinstance(other, SubmoduleImportation):
            # See note in SubmoduleImportation about RedefinedWhileUnused
            return self.fullName == other.fullName
        return isinstance(other, Definition) and self.name == other.name

    def _has_alias(self):
        return not self.fullName.split(".")[-1] == self.name

    @property
    def source_statement(self):
        if self._has_alias():
            return "import %s as %s" % (self.fullName, self.name)
        else:
            return "import %s" % self.fullName

    def __str__(self):
        if self._has_alias():
            return self.fullName + " as " + self.name
        else:
            return self.fullName


class SubmoduleImportation(Importation):
    def __init__(self, name, source):
        # A dot should only appear in the name when it is a submodule import
        assert "." in name and (not source or isinstance(source, ast.Import))
        package_name = name.split(".")[0]
        super(SubmoduleImportation, self).__init__(package_name, source)
        self.fullName = name

    def redefines(self, other):
        if isinstance(other, Importation):
            return self.fullName == other.fullName
        return super(SubmoduleImportation, self).redefines(other)

    def __str__(self):
        return self.fullName

    @property
    def source_statement(self):
        return "import " + self.fullName


class ImportationFrom(Importation):
    def __init__(self, name, source, module, real_name=None):
        self.module = module
        self.real_name = real_name or name

        if module.endswith("."):
            full_name = module + self.real_name
        else:
            full_name = module + "." + self.real_name

        super(ImportationFrom, self).__init__(name, source, full_name)

    def __str__(self):
        if self.real_name != self.name:
            return self.fullName + " as " + self.name
        else:
            return self.fullName

    @property
    def source_statement(self):
        if self.real_name != self.name:
            return "from %s import %s as %s" % (
                self.module,
                self.real_name,
                self.name,
            )
        else:
            return "from %s import %s" % (self.module, self.name)


class StarImportation(Importation):
    def __init__(self, name, source):
        super(StarImportation, self).__init__("*", source)
        # Each star importation needs a unique name, and
        # may not be the module name otherwise it will be deemed imported
        self.name = name + ".*"
        self.fullName = name

    @property
    def source_statement(self):
        return "from " + self.fullName + " import *"

    def __str__(self):
        # When the module ends with a ., avoid the ambiguous '..*'
        if self.fullName.endswith("."):
            return self.source_statement
        else:
            return self.name


class FutureImportation(ImportationFrom):
    def __init__(self, name, source, scope):
        super(FutureImportation, self).__init__(name, source, "__future__")
        self.used = (scope, source)


class Argument(Binding):
    """Represents binding a name as an argument."""


class Assignment(Binding):
    """
    Represents binding a name with an explicit assignment.

    The checker will raise warnings for any Assignment that isn't used. Also,
    the checker does not consider assignments in tuple/list unpacking to be
    Assignments, rather it treats them as simple Bindings.
    """


class FunctionDefinition(Definition):
    pass


class ClassDefinition(Definition):
    pass


class ExportBinding(Binding):
    def __init__(self, name, source, scope):
        if "__all__" in scope and isinstance(source, ast.AugAssign):
            self.names = list(scope["__all__"].names)
        else:
            self.names = []

        def _add_to_names(container):
            for node in container.elts:
                if isinstance(node, ast.Str):
                    self.names.append(node.s)

        if isinstance(source.value, (ast.List, ast.Tuple)):
            _add_to_names(source.value)
        # If concatenating lists
        elif isinstance(source.value, ast.BinOp):
            currentValue = source.value
            while isinstance(currentValue.right, ast.List):
                left = currentValue.left
                right = currentValue.right
                _add_to_names(right)
                # If more lists are being added
                if isinstance(left, ast.BinOp):
                    currentValue = left
                # If just two lists are being added
                elif isinstance(left, ast.List):
                    _add_to_names(left)
                    # All lists accounted for - done
                    break
                # If not list concatenation
                else:
                    break
        super(ExportBinding, self).__init__(name, source)


class Scope(dict):
    importStarred = False

    def __repr__(self):
        scope_cls = self.__class__.__name__
        return "<%s at 0x%x %s>" % (scope_cls, id(self), dict.__repr__(self))


class ClassScope(Scope):
    pass


class FunctionScope(Scope):
    usesLocals = False
    alwaysUsed = {
        "__tracebackhide__",
        "__traceback_info__",
        "__traceback_supplement__",
    }

    def __init__(self):
        super(FunctionScope, self).__init__()
        # Simplify: manage the special locals as globals
        self.globals = self.alwaysUsed.copy()
        self.returnValue = None  # First non-empty return
        self.isGenerator = False  # Detect a generator

    def unusedAssignments(self):
        for name, binding in self.items():
            if (
                not binding.used
                and name != "_"
                and name not in self.globals  # see issue #202
                and not self.usesLocals
                and isinstance(binding, Assignment)
            ):
                yield name, binding


class GeneratorScope(Scope):
    pass


class ModuleScope(Scope):
    _futures_allowed = True
    _annotations_future_enabled = False


class DoctestScope(ModuleScope):
    """Scope for a doctest."""


class DummyNode:
    def __init__(self, lineno, col_offset):
        self.lineno = lineno
        self.col_offset = col_offset


# Globally defined names which are not attributes of the builtins module, or
# are only present on some platforms.
_MAGIC_GLOBALS = ["__file__", "__builtins__", "WindowsError"]
# module scope annotation will store in `__annotations__`, see also PEP 526.
if PY36_PLUS:
    _MAGIC_GLOBALS.append("__annotations__")


def getNodeName(node):
    # Returns node.id, or node.name, or None
    if hasattr(node, "id"):  # One of the many nodes with an id
        return node.id
    if hasattr(node, "name"):  # an ExceptHandler node
        return node.name


def is_typing_overload(value, scope_stack):
    def name_is_typing_overload(name):  # type: (str) -> bool
        for scope in reversed(scope_stack):
            if name in scope:
                return isinstance(scope[name], ImportationFrom) and scope[
                    name
                ].fullName in (
                    "typing.overload",
                    "typing_extensions.overload",
                )

        return False

    def is_typing_overload_decorator(node):
        return (
            isinstance(node, ast.Name) and name_is_typing_overload(node.id)
        ) or (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "typing"
            and node.attr == "overload"
        )

    return isinstance(value.source, FUNCTION_TYPES) and any(
        is_typing_overload_decorator(dec)
        for dec in value.source.decorator_list
    )


def make_tokens(code):
    # PY3: tokenize.tokenize requires readline of bytes
    if not isinstance(code, bytes):
        code = code.encode("UTF-8")
    lines = iter(code.splitlines(True))
    # next(lines, b'') is to prevent an error in pypy3
    return tuple(tokenize.tokenize(lambda: next(lines, b"")))


class _TypeableVisitor(ast.NodeVisitor):
    def __init__(self):
        self.typeable_lines = []
        self.typeable_nodes = {}

    def _typeable(self, node):
        # if there is more than one typeable thing on a line last one wins
        self.typeable_lines.append(node.lineno)
        self.typeable_nodes[node.lineno] = node

        self.generic_visit(node)

    visit_Assign = visit_For = visit_FunctionDef = visit_With = _typeable
    visit_AsyncFor = visit_AsyncFunctionDef = visit_AsyncWith = _typeable


def _collect_type_comments(tree, tokens):
    visitor = _TypeableVisitor()
    visitor.visit(tree)

    type_comments = collections.defaultdict(list)
    for tp, text, start, _, _ in tokens:
        if (
            tp != tokenize.COMMENT
            or not TYPE_COMMENT_RE.match(text)  # skip non comments
            or TYPE_IGNORE_RE.match(  # skip non-type comments
                text
            )  # skip ignores
        ):
            continue

        # search for the typeable node at or before the line number of the
        # type comment.
        # if the bisection insertion point is before any nodes this is an
        # invalid type comment which is ignored.
        lineno, _ = start
        idx = bisect.bisect_right(visitor.typeable_lines, lineno)
        if idx == 0:
            continue
        node = visitor.typeable_nodes[visitor.typeable_lines[idx - 1]]
        type_comments[node].append((start, text))

    return type_comments


class Checker:
    _ast_node_scope = {
        ast.Module: ModuleScope,
        ast.ClassDef: ClassScope,
        ast.FunctionDef: FunctionScope,
        ast.Lambda: FunctionScope,
        ast.ListComp: GeneratorScope,
        ast.SetComp: GeneratorScope,
        ast.GeneratorExp: GeneratorScope,
        ast.DictComp: GeneratorScope,
    }
    if PY35_PLUS:
        _ast_node_scope[ast.AsyncFunctionDef] = FunctionScope

    nodeDepth = 0
    offset = None
    traceTree = False

    builtIns = set(builtin_vars).union(_MAGIC_GLOBALS)

    def __init__(
        self,
        tree,
        builtins=None,
        withDoctest="PYFLAKES_DOCTEST" in os.environ,
        file_tokens=(),
        filename="",
    ):
        self._nodeHandlers = {}
        self._deferredFunctions = []
        self._deferredAssignments = []
        self.deadScopes = []
        self.messages = []
        self.filename = filename
        if builtins:
            self.builtIns = self.builtIns.union(builtins)
        self.withDoctest = withDoctest
        try:
            self.scopeStack = [Checker._ast_node_scope[type(tree)]()]
        except KeyError:
            raise RuntimeError("No scope implemented for the node %r" % tree)
        self.exceptHandlers = [()]
        self.root = tree
        self._type_comments = _collect_type_comments(tree, file_tokens)
        for builtin in self.builtIns:
            self.addBinding(None, Builtin(builtin))
        self.handleChildren(tree)
        self.runDeferred(self._deferredFunctions)
        # Set _deferredFunctions to None so that deferFunction will fail
        # noisily if called after we've run through the deferred functions.
        self._deferredFunctions = None
        self.runDeferred(self._deferredAssignments)
        # Set _deferredAssignments to None so that deferAssignment will fail
        # noisily if called after we've run through the deferred assignments.
        self._deferredAssignments = None
        del self.scopeStack[1:]
        self.popScope()
        self.checkDeadScopes()

    def deferFunction(self, callable):
        self._deferredFunctions.append(
            (callable, self.scopeStack[:], self.offset)
        )

    def deferAssignment(self, callable):
        self._deferredAssignments.append(
            (callable, self.scopeStack[:], self.offset)
        )

    def runDeferred(self, deferred):
        for handler, scope, offset in deferred:
            self.scopeStack = scope
            self.offset = offset
            handler()

    def _in_doctest(self):
        return len(self.scopeStack) >= 2 and isinstance(
            self.scopeStack[1], DoctestScope
        )

    @property
    def futuresAllowed(self):
        if not all(
            isinstance(scope, ModuleScope) for scope in self.scopeStack
        ):
            return False

        return self.scope._futures_allowed

    @futuresAllowed.setter
    def futuresAllowed(self, value):
        assert value is False
        if isinstance(self.scope, ModuleScope):
            self.scope._futures_allowed = False

    @property
    def annotationsFutureEnabled(self):
        scope = self.scopeStack[0]
        if not isinstance(scope, ModuleScope):
            return False
        return scope._annotations_future_enabled

    @annotationsFutureEnabled.setter
    def annotationsFutureEnabled(self, value):
        assert value is True
        assert isinstance(self.scope, ModuleScope)
        self.scope._annotations_future_enabled = True

    @property
    def scope(self):
        return self.scopeStack[-1]

    def popScope(self):
        self.deadScopes.append(self.scopeStack.pop())

    def checkDeadScopes(self):
        for scope in self.deadScopes:
            # imports in classes are public members
            if isinstance(scope, ClassScope):
                continue

            all_binding = scope.get("__all__")
            if all_binding and not isinstance(all_binding, ExportBinding):
                all_binding = None

            if all_binding:
                all_names = set(all_binding.names)
                undefined = all_names.difference(scope)
            else:
                all_names = undefined = []

            if undefined:
                if (
                    not scope.importStarred
                    and os.path.basename(self.filename) != "__init__.py"
                ):
                    # Look for possible mistakes in the export list
                    for name in undefined:
                        self.report(
                            messages.UndefinedExport,
                            scope["__all__"].source,
                            name,
                        )

                # mark all import '*' as used by the undefined in __all__
                if scope.importStarred:
                    from_list = []
                    for binding in scope.values():
                        if isinstance(binding, StarImportation):
                            binding.used = all_binding
                            from_list.append(binding.fullName)
                    # report * usage, with a list of possible sources
                    from_list = ", ".join(sorted(from_list))
                    for name in undefined:
                        self.report(
                            messages.ImportStarUsage,
                            scope["__all__"].source,
                            name,
                            from_list,
                        )

            # Look for imported names that aren't used.
            for value in scope.values():
                if isinstance(value, Importation):
                    used = value.used or value.name in all_names
                    if not used:
                        messg = messages.UnusedImport
                        self.report(messg, value.source, str(value))
                    for node in value.redefined:
                        if isinstance(self.getParent(node), FOR_TYPES):
                            messg = messages.ImportShadowedByLoopVar
                        elif used:
                            continue
                        else:
                            messg = messages.RedefinedWhileUnused
                        self.report(messg, node, value.name, value.source)

    def pushScope(self, scopeClass=FunctionScope):
        self.scopeStack.append(scopeClass())

    def report(self, messageClass, *args, **kwargs):
        self.messages.append(messageClass(*args, **kwargs))

    def getParent(self, node):
        # Lookup the first parent which is not Tuple, List or Starred
        while True:
            node = node._pyflakes_parent
            if not hasattr(node, "elts") and not hasattr(node, "ctx"):
                return node

    def getCommonAncestor(self, lnode, rnode, stop):
        if stop in (lnode, rnode) or not (
            hasattr(lnode, "_pyflakes_parent")
            and hasattr(rnode, "_pyflakes_parent")
        ):
            return None
        if lnode is rnode:
            return lnode

        if lnode._pyflakes_depth > rnode._pyflakes_depth:
            return self.getCommonAncestor(lnode._pyflakes_parent, rnode, stop)
        if lnode._pyflakes_depth < rnode._pyflakes_depth:
            return self.getCommonAncestor(lnode, rnode._pyflakes_parent, stop)
        return self.getCommonAncestor(
            lnode._pyflakes_parent, rnode._pyflakes_parent, stop,
        )

    def descendantOf(self, node, ancestors, stop):
        for a in ancestors:
            if self.getCommonAncestor(node, a, stop):
                return True
        return False

    def _getAncestor(self, node, ancestor_type):
        parent = node
        while True:
            if parent is self.root:
                return None
            parent = self.getParent(parent)
            if isinstance(parent, ancestor_type):
                return parent

    def getScopeNode(self, node):
        return self._getAncestor(node, tuple(Checker._ast_node_scope.keys()))

    def differentForks(self, lnode, rnode):
        ancestor = self.getCommonAncestor(lnode, rnode, self.root)
        parts = getAlternatives(ancestor)
        if parts:
            for items in parts:
                if self.descendantOf(
                    lnode, items, ancestor
                ) ^ self.descendantOf(rnode, items, ancestor):
                    return True
        return False

    def addBinding(self, node, value):
        # assert value.source in (node, node._pyflakes_parent):
        for scope in self.scopeStack[::-1]:
            if value.name in scope:
                break
        existing = scope.get(value.name)

        if (
            existing
            and not isinstance(existing, Builtin)
            and not self.differentForks(node, existing.source)
        ):

            parent_stmt = self.getParent(value.source)
            if isinstance(existing, Importation) and isinstance(
                parent_stmt, FOR_TYPES
            ):
                self.report(
                    messages.ImportShadowedByLoopVar,
                    node,
                    value.name,
                    existing.source,
                )

            elif scope is self.scope:
                if isinstance(
                    parent_stmt, ast.comprehension
                ) and not isinstance(
                    self.getParent(existing.source),
                    (FOR_TYPES, ast.comprehension),
                ):
                    self.report(
                        messages.RedefinedInListComp,
                        node,
                        value.name,
                        existing.source,
                    )
                elif not existing.used and value.redefines(existing):
                    if value.name != "_" or isinstance(existing, Importation):
                        if not is_typing_overload(existing, self.scopeStack):
                            self.report(
                                messages.RedefinedWhileUnused,
                                node,
                                value.name,
                                existing.source,
                            )

            elif isinstance(existing, Importation) and value.redefines(
                existing
            ):
                existing.redefined.append(node)

        if value.name in self.scope:
            # then assume the rebound name is used as a global or within a loop
            value.used = self.scope[value.name].used

        self.scope[value.name] = value

    def getNodeHandler(self, node_class):
        try:
            return self._nodeHandlers[node_class]
        except KeyError:
            nodeType = getNodeType(node_class)
        self._nodeHandlers[node_class] = handler = getattr(self, nodeType)
        return handler

    def handleNodeLoad(self, node):
        name = getNodeName(node)
        if not name:
            return

        in_generators = None
        importStarred = None

        # try enclosing function scopes and global scope
        for scope in self.scopeStack[-1::-1]:
            if isinstance(scope, ClassScope):
                if name == "__class__":
                    return
                elif in_generators is False:
                    # only generators used in a class scope can access the
                    # names of the class. this is skipped during the first
                    # iteration
                    continue

            if name == "print" and isinstance(scope.get(name, None), Builtin):
                parent = self.getParent(node)
                if isinstance(parent, ast.BinOp) and isinstance(
                    parent.op, ast.RShift
                ):
                    self.report(messages.InvalidPrintSyntax, node)

            try:
                scope[name].used = (self.scope, node)

                # if the name of SubImportation is same as
                # alias of other Importation and the alias
                # is used, SubImportation also should be marked as used.
                n = scope[name]
                if isinstance(n, Importation) and n._has_alias():
                    try:
                        scope[n.fullName].used = (self.scope, node)
                    except KeyError:
                        pass
            except KeyError:
                pass
            else:
                return

            importStarred = importStarred or scope.importStarred

            if in_generators is not False:
                in_generators = isinstance(scope, GeneratorScope)

        if importStarred:
            from_list = []

            for scope in self.scopeStack[-1::-1]:
                for binding in scope.values():
                    if isinstance(binding, StarImportation):
                        # mark '*' imports as used for each scope
                        binding.used = (self.scope, node)
                        from_list.append(binding.fullName)

            # report * usage, with a list of possible sources
            from_list = ", ".join(sorted(from_list))
            self.report(messages.ImportStarUsage, node, name, from_list)
            return

        if (
            name == "__path__"
            and os.path.basename(self.filename) == "__init__.py"
        ):
            # the special name __path__ is valid only in packages
            return

        if name == "__module__" and isinstance(self.scope, ClassScope):
            return

        # protected with a NameError handler?
        if "NameError" not in self.exceptHandlers[-1]:
            self.report(messages.UndefinedName, node, name)

    def handleNodeStore(self, node):
        name = getNodeName(node)
        if not name:
            return
        # if the name hasn't already been defined in the current scope
        if isinstance(self.scope, FunctionScope) and name not in self.scope:
            # for each function or module scope above us
            for scope in self.scopeStack[:-1]:
                if not isinstance(scope, (FunctionScope, ModuleScope)):
                    continue
                # if the name was defined in that scope, and the name has
                # been accessed already in the current scope, and hasn't
                # been declared global
                used = name in scope and scope[name].used
                if (
                    used
                    and used[0] is self.scope
                    and name not in self.scope.globals
                ):
                    # then it's probably a mistake
                    break

        parent_stmt = self.getParent(node)
        if isinstance(parent_stmt, (FOR_TYPES, ast.comprehension)) or (
            parent_stmt != node._pyflakes_parent
            and not self.isLiteralTupleUnpacking(parent_stmt)
        ):
            binding = Binding(name, node)
        elif name == "__all__" and isinstance(self.scope, ModuleScope):
            binding = ExportBinding(name, node._pyflakes_parent, self.scope)
        elif isinstance(getattr(node, "ctx", None), ast.Param):
            binding = Argument(name, self.getScopeNode(node))
        else:
            binding = Assignment(name, node)
        self.addBinding(node, binding)

    def handleNodeDelete(self, node):
        def on_conditional_branch():
            current = getattr(node, "_pyflakes_parent", None)
            while current:
                if isinstance(current, (ast.If, ast.While, ast.IfExp)):
                    return True
                current = getattr(current, "_pyflakes_parent", None)
            return False

        name = getNodeName(node)
        if not name:
            return

        if on_conditional_branch():
            # We cannot predict if this conditional branch is going to
            # be executed.
            return

        if (
            isinstance(self.scope, FunctionScope)
            and name in self.scope.globals
        ):
            self.scope.globals.remove(name)
        else:
            try:
                del self.scope[name]
            except KeyError:
                self.report(messages.UndefinedName, node, name)

    def handleChildren(self, tree, omit=None):
        for node in iter_child_nodes(tree, omit=omit):
            self.handleNode(node, tree)

    def isLiteralTupleUnpacking(self, node):
        if isinstance(node, ast.Assign):
            for child in node.targets + [node.value]:
                if not hasattr(child, "elts"):
                    return False
            return True

    def isDocstring(self, node):
        return isinstance(node, ast.Str) or (
            isinstance(node, ast.Expr) and isinstance(node.value, ast.Str)
        )

    def getDocstring(self, node):
        if isinstance(node, ast.Expr):
            node = node.value
        if not isinstance(node, ast.Str):
            return (None, None)

        if PYPY or PY38_PLUS:
            doctest_lineno = node.lineno - 1
        else:
            # Computed incorrectly if the docstring has backslash
            doctest_lineno = node.lineno - node.s.count("\n") - 1

        return (node.s, doctest_lineno)

    def handleNode(self, node, parent):
        if node is None:
            return
        if self.offset and getattr(node, "lineno", None) is not None:
            node.lineno += self.offset[0]
            node.col_offset += self.offset[1]
        if self.traceTree:
            print("  " * self.nodeDepth + node.__class__.__name__)
        if self.futuresAllowed and not (
            isinstance(node, ast.ImportFrom) or self.isDocstring(node)
        ):
            self.futuresAllowed = False
        self.nodeDepth += 1
        node._pyflakes_depth = self.nodeDepth
        node._pyflakes_parent = parent
        try:
            handler = self.getNodeHandler(node.__class__)
            handler(node)
        finally:
            self.nodeDepth -= 1
        if self.traceTree:
            print("  " * self.nodeDepth + "end " + node.__class__.__name__)

    _getDoctestExamples = doctest.DocTestParser().get_examples

    def handleDoctests(self, node):
        try:
            if hasattr(node, "docstring"):
                docstring = node.docstring

                # This is just a reasonable guess. In Python 3.7, docstrings no
                # longer have line numbers associated with them. This will be
                # incorrect if there are empty lines between the beginning
                # of the function and the docstring.
                node_lineno = node.lineno
                if hasattr(node, "args"):
                    node_lineno = max(
                        [node_lineno] + [arg.lineno for arg in node.args.args]
                    )
            else:
                (docstring, node_lineno) = self.getDocstring(node.body[0])
            examples = docstring and self._getDoctestExamples(docstring)
        except (ValueError, IndexError):
            # e.g. line 6 of the docstring for <string> has inconsistent
            # leading whitespace: ...
            return
        if not examples:
            return

        # Place doctest in module scope
        saved_stack = self.scopeStack
        self.scopeStack = [self.scopeStack[0]]
        node_offset = self.offset or (0, 0)
        self.pushScope(DoctestScope)
        if "_" not in self.scopeStack[0]:
            self.addBinding(None, Builtin("_"))
        for example in examples:
            try:
                tree = ast.parse(example.source, "<doctest>")
            except SyntaxError:
                e = sys.exc_info()[1]
                if PYPY:
                    e.offset += 1
            else:
                self.offset = (
                    node_offset[0] + node_lineno + example.lineno,
                    node_offset[1] + example.indent + 4,
                )
                self.handleChildren(tree)
                self.offset = node_offset
        self.popScope()
        self.scopeStack = saved_stack

    def handleStringAnnotation(self, s, node, ref_lineno, ref_col_offset, err):
        try:
            tree = ast.parse(s)
        except SyntaxError:
            self.report(err, node, s)
            return

        body = tree.body
        if len(body) != 1 or not isinstance(body[0], ast.Expr):
            self.report(err, node, s)
            return

        parsed_annotation = tree.body[0].value
        for descendant in ast.walk(parsed_annotation):
            if (
                "lineno" in descendant._attributes
                and "col_offset" in descendant._attributes
            ):
                descendant.lineno = ref_lineno
                descendant.col_offset = ref_col_offset

        self.handleNode(parsed_annotation, node)

    def handleAnnotation(self, annotation, node):
        if self.annotationsFutureEnabled:
            self.deferFunction(lambda: self.handleNode(annotation, node))
        else:
            self.handleNode(annotation, node)

    def ignore(self, node):
        pass

    # "stmt" type nodes
    DELETE = (
        PRINT
    ) = (
        FOR
    ) = (
        ASYNCFOR
    ) = (
        WHILE
    ) = (
        IF
    ) = (
        WITH
    ) = (
        WITHITEM
    ) = (
        ASYNCWITH
    ) = ASYNCWITHITEM = TRYFINALLY = EXEC = EXPR = ASSIGN = handleChildren

    PASS = ignore

    # "expr" type nodes
    BOOLOP = (
        UNARYOP
    ) = (
        IFEXP
    ) = (
        SET
    ) = (
        REPR
    ) = (
        ATTRIBUTE
    ) = SUBSCRIPT = STARRED = NAMECONSTANT = NAMEDEXPR = handleChildren

    def _handle_string_dot_format(self, node):
        try:
            placeholders = tuple(parse_format_string(node.func.value.s))
        except ValueError as e:
            self.report(messages.StringDotFormatInvalidFormat, node, e)
            return

        class state:  # py2-compatible `nonlocal`
            auto = None
            next_auto = 0

        placeholder_positional = set()
        placeholder_named = set()

        def _add_key(fmtkey):
            if fmtkey is None:  # end of string or `{` / `}` escapes
                return False

            # attributes / indices are allowed in `.format(...)`
            fmtkey, _, _ = fmtkey.partition(".")
            fmtkey, _, _ = fmtkey.partition("[")

            try:
                fmtkey = int(fmtkey)
            except ValueError:
                pass
            else:  # fmtkey was an integer
                if state.auto is True:
                    self.report(messages.StringDotFormatMixingAutomatic, node)
                    return True
                else:
                    state.auto = False

            if fmtkey == "":
                if state.auto is False:
                    self.report(messages.StringDotFormatMixingAutomatic, node)
                    return True
                else:
                    state.auto = True

                fmtkey = state.next_auto
                state.next_auto += 1

            if isinstance(fmtkey, int):
                placeholder_positional.add(fmtkey)
            else:
                placeholder_named.add(fmtkey)

            return False

        for _, fmtkey, spec, _ in placeholders:
            if _add_key(fmtkey):
                return

            # spec can also contain format specifiers
            if spec is not None:
                try:
                    spec_placeholders = tuple(parse_format_string(spec))
                except ValueError as e:
                    self.report(messages.StringDotFormatInvalidFormat, node, e)
                    return

                for _, spec_fmtkey, spec_spec, _ in spec_placeholders:
                    # can't recurse again
                    if spec_spec is not None and "{" in spec_spec:
                        self.report(
                            messages.StringDotFormatInvalidFormat,
                            node,
                            "Max string recursion exceeded",
                        )
                        return
                    if _add_key(spec_fmtkey):
                        return

        # bail early if there is *args or **kwargs
        if (
            # python 2.x *args / **kwargs
            getattr(node, "starargs", None)
            or getattr(node, "kwargs", None)
            or
            # python 3.x *args
            any(
                isinstance(arg, getattr(ast, "Starred", ()))
                for arg in node.args
            )
            or
            # python 3.x **kwargs
            any(kwd.arg is None for kwd in node.keywords)
        ):
            return

        substitution_positional = set(range(len(node.args)))
        substitution_named = {kwd.arg for kwd in node.keywords}

        extra_positional = substitution_positional - placeholder_positional
        extra_named = substitution_named - placeholder_named

        if extra_positional:
            self.report(
                messages.StringDotFormatExtraPositionalArguments,
                node,
                ", ".join(sorted(str(x) for x in extra_positional)),
            )
        if extra_named:
            self.report(
                messages.StringDotFormatExtraNamedArguments,
                node,
                ", ".join(sorted(extra_named)),
            )

    def CALL(self, node):
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Str)
            and node.func.attr == "format"
        ):
            self._handle_string_dot_format(node)
        self.handleChildren(node)

    def _handle_percent_format(self, node):
        try:
            placeholders = parse_percent_format(node.left.s)
        except ValueError:
            return

        named = set()
        positional_count = 0
        positional = None
        for _, placeholder in placeholders:
            if placeholder is None:
                continue
            name, _, width, precision, conversion = placeholder

            if conversion == "%":
                continue

            if positional is None and conversion:
                positional = name is None

            for part in (width, precision):
                if part is not None and "*" in part:
                    if positional:
                        positional_count += 1

            if positional and name is not None:
                return
            elif not positional and name is None:
                return

            if positional:
                positional_count += 1
            else:
                named.add(name)

        if isinstance(node.right, ast.Dict) and all(
            isinstance(k, ast.Str) for k in node.right.keys
        ):
            if positional and positional_count > 1:
                return

            substitution_keys = {k.s for k in node.right.keys}
            extra_keys = substitution_keys - named
            missing_keys = named - substitution_keys
            if not positional and extra_keys:
                self.report(
                    messages.PercentFormatExtraNamedArguments,
                    node,
                    ", ".join(sorted(extra_keys)),
                )
            if not positional and missing_keys:
                self.report(
                    messages.PercentFormatMissingArgument,
                    node,
                    ", ".join(sorted(missing_keys)),
                )

    def BINOP(self, node):
        if isinstance(node.op, ast.Mod) and isinstance(node.left, ast.Str):
            self._handle_percent_format(node)
        self.handleChildren(node)

    NUM = STR = BYTES = ELLIPSIS = CONSTANT = ignore

    # "slice" type nodes
    SLICE = EXTSLICE = INDEX = handleChildren

    # expression contexts are node instances too, though being constants
    LOAD = STORE = DEL = AUGLOAD = AUGSTORE = PARAM = ignore

    # same for operators
    AND = (
        OR
    ) = (
        ADD
    ) = (
        SUB
    ) = (
        MULT
    ) = (
        DIV
    ) = (
        MOD
    ) = (
        POW
    ) = (
        LSHIFT
    ) = (
        RSHIFT
    ) = (
        BITOR
    ) = (
        BITXOR
    ) = (
        BITAND
    ) = (
        FLOORDIV
    ) = (
        INVERT
    ) = (
        NOT
    ) = (
        UADD
    ) = (
        USUB
    ) = (
        EQ
    ) = (
        NOTEQ
    ) = LT = LTE = GT = GTE = IS = ISNOT = IN = NOTIN = MATMULT = ignore

    def RAISE(self, node):
        self.handleChildren(node)

        arg = get_raise_argument(node)

        if isinstance(arg, ast.Call):
            if is_notimplemented_name_node(arg.func):
                # Handle "raise NotImplemented(...)"
                self.report(messages.RaiseNotImplemented, node)
        elif is_notimplemented_name_node(arg):
            # Handle "raise NotImplemented"
            self.report(messages.RaiseNotImplemented, node)

    # additional node types
    COMPREHENSION = KEYWORD = FORMATTEDVALUE = handleChildren

    _in_fstring = False

    def JOINEDSTR(self, node):
        if (
            # the conversion / etc. flags are parsed as f-strings without
            # placeholders
            not self._in_fstring
            and not any(isinstance(x, ast.FormattedValue) for x in node.values)
        ):
            self.report(messages.FStringMissingPlaceholders, node)

        self._in_fstring, orig = True, self._in_fstring
        try:
            self.handleChildren(node)
        finally:
            self._in_fstring = orig

    def DICT(self, node):
        keys = [convert_to_value(key) for key in node.keys]

        key_counts = counter(keys)
        duplicate_keys = [
            key for key, count in key_counts.items() if count > 1
        ]

        for key in duplicate_keys:
            key_indices = [i for i, i_key in enumerate(keys) if i_key == key]

            values = counter(
                convert_to_value(node.values[index]) for index in key_indices
            )
            if any(count == 1 for value, count in values.items()):
                for key_index in key_indices:
                    key_node = node.keys[key_index]
                    if isinstance(key, VariableKey):
                        self.report(
                            messages.MultiValueRepeatedKeyVariable,
                            key_node,
                            key.name,
                        )
                    else:
                        self.report(
                            messages.MultiValueRepeatedKeyLiteral,
                            key_node,
                            key,
                        )
        self.handleChildren(node)

    def ASSERT(self, node):
        if isinstance(node.test, ast.Tuple) and node.test.elts != []:
            self.report(messages.AssertTuple, node)
        self.handleChildren(node)

    def GLOBAL(self, node):
        global_scope_index = 1 if self._in_doctest() else 0
        global_scope = self.scopeStack[global_scope_index]

        # Ignore 'global' statement in global scope.
        if self.scope is not global_scope:

            # One 'global' statement can bind multiple (comma-delimited) names.
            for node_name in node.names:
                node_value = Assignment(node_name, node)

                # Remove UndefinedName messages already reported for this name.
                # TODO: if the global is not used in this scope, it does not
                # become a globally defined name.  See test_unused_global.
                self.messages = [
                    m
                    for m in self.messages
                    if not isinstance(m, messages.UndefinedName)
                    or m.message_args[0] != node_name
                ]

                # Bind name to global scope if it doesn't exist already.
                global_scope.setdefault(node_name, node_value)

                # Bind name to non-global scopes, but as already "used".
                node_value.used = (global_scope, node)
                for scope in self.scopeStack[global_scope_index + 1:]:
                    scope[node_name] = node_value

    NONLOCAL = GLOBAL

    def GENERATOREXP(self, node):
        self.pushScope(GeneratorScope)
        self.handleChildren(node)
        self.popScope()

    LISTCOMP = GENERATOREXP

    DICTCOMP = SETCOMP = GENERATOREXP

    def NAME(self, node):
        # Locate the name in locals / function / globals scopes.
        if isinstance(node.ctx, (ast.Load, ast.AugLoad)):
            self.handleNodeLoad(node)
            if (
                node.id == "locals"
                and isinstance(self.scope, FunctionScope)
                and isinstance(node._pyflakes_parent, ast.Call)
            ):
                # we are doing locals() call in current scope
                self.scope.usesLocals = True
        elif isinstance(node.ctx, (ast.Store, ast.AugStore, ast.Param)):
            self.handleNodeStore(node)
        elif isinstance(node.ctx, ast.Del):
            self.handleNodeDelete(node)
        else:
            # Unknown context
            raise RuntimeError(
                "Got impossible expression context: %r" % (node.ctx)
            )

    def CONTINUE(self, node):
        # Walk the tree up until we see a loop (OK), a function or class
        # definition (not OK), for 'continue', a finally block (not OK), or
        # the top module scope (not OK)
        n = node
        while hasattr(n, "_pyflakes_parent"):
            n, n_child = n._pyflakes_parent, n
            if isinstance(n, LOOP_TYPES):
                # Doesn't apply unless it's in the loop itself
                if n_child not in n.orelse:
                    return
            if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
                break

    BREAK = CONTINUE

    def RETURN(self, node):
        if (
            node.value
            and hasattr(self.scope, "returnValue")
            and not self.scope.returnValue
        ):
            self.scope.returnValue = node.value
        self.handleNode(node.value, node)

    def YIELD(self, node):
        self.scope.isGenerator = True
        self.handleNode(node.value, node)

    AWAIT = YIELDFROM = YIELD

    def FUNCTIONDEF(self, node):
        for deco in node.decorator_list:
            self.handleNode(deco, node)
        self.LAMBDA(node)
        self.addBinding(node, FunctionDefinition(node.name, node))
        # doctest does not process doctest within a doctest,
        # or in nested functions.
        if (
            self.withDoctest
            and not self._in_doctest()
            and not isinstance(self.scope, FunctionScope)
        ):
            self.deferFunction(lambda: self.handleDoctests(node))

    ASYNCFUNCTIONDEF = FUNCTIONDEF

    def LAMBDA(self, node):
        args = []
        annotations = []

        if PY38_PLUS:
            for arg in node.args.posonlyargs:
                args.append(arg.arg)
                annotations.append(arg.annotation)
        for arg in node.args.args + node.args.kwonlyargs:
            args.append(arg.arg)
            annotations.append(arg.annotation)
        defaults = node.args.defaults + node.args.kw_defaults

        # Only for Python3 FunctionDefs
        is_py3_func = hasattr(node, "returns")

        for arg_name in ("vararg", "kwarg"):
            wildcard = getattr(node.args, arg_name)
            if not wildcard:
                continue
            args.append(wildcard.arg)
            if is_py3_func:
                annotations.append(wildcard.annotation)

        if is_py3_func:
            annotations.append(node.returns)

        if len(set(args)) < len(args):
            for (idx, arg) in enumerate(args):
                if arg in args[:idx]:
                    self.report(messages.DuplicateArgument, node, arg)

        for annotation in annotations:
            self.handleAnnotation(annotation, node)

        for default in defaults:
            self.handleNode(default, node)

        def runFunction():
            self.pushScope()

            self.handleChildren(node, omit=["decorator_list", "returns"])

            def checkUnusedAssignments():
                for name, binding in self.scope.unusedAssignments():
                    self.report(messages.UnusedVariable, binding.source, name)

            self.deferAssignment(checkUnusedAssignments)

            self.popScope()

        self.deferFunction(runFunction)

    def ARGUMENTS(self, node):
        self.handleChildren(node, omit=("defaults", "kw_defaults"))

    def ARG(self, node):
        self.addBinding(node, Argument(node.arg, self.getScopeNode(node)))

    def CLASSDEF(self, node):
        for deco in node.decorator_list:
            self.handleNode(deco, node)
        for baseNode in node.bases:
            self.handleNode(baseNode, node)
        for keywordNode in node.keywords:
            self.handleNode(keywordNode, node)
        self.pushScope(ClassScope)
        # doctest does not process doctest within a doctest
        # classes within classes are processed.
        if (
            self.withDoctest
            and not self._in_doctest()
            and not isinstance(self.scope, FunctionScope)
        ):
            self.deferFunction(lambda: self.handleDoctests(node))
        for stmt in node.body:
            self.handleNode(stmt, node)
        self.popScope()
        self.addBinding(node, ClassDefinition(node.name, node))

    def AUGASSIGN(self, node):
        self.handleNodeLoad(node.target)
        self.handleNode(node.value, node)
        self.handleNode(node.target, node)

    def TUPLE(self, node):
        if isinstance(node.ctx, ast.Store):
            # Python 3 advanced tuple unpacking: a, *b, c = d.
            # Only one starred expression is allowed, and no more than 1<<8
            # assignments are allowed before a stared expression. There is
            # also a limit of 1<<24 expressions after the starred expression,
            # which is impossible to test due to memory restrictions, but we
            # add it here anyway
            has_starred = False
            star_loc = -1
            for i, n in enumerate(node.elts):
                if isinstance(n, ast.Starred):
                    if has_starred:
                        self.report(messages.TwoStarredExpressions, node)
                        # The SyntaxError doesn't distinguish two from more
                        # than two.
                        break
                    has_starred = True
                    star_loc = i
            if star_loc >= 1 << 8 or len(node.elts) - star_loc - 1 >= 1 << 24:
                self.report(
                    messages.TooManyExpressionsInStarredAssignment, node
                )
        self.handleChildren(node)

    LIST = TUPLE

    def IMPORT(self, node):
        for alias in node.names:
            if "." in alias.name and not alias.asname:
                importation = SubmoduleImportation(alias.name, node)
            else:
                name = alias.asname or alias.name
                importation = Importation(name, node, alias.name)
            self.addBinding(node, importation)

    def IMPORTFROM(self, node):
        if node.module == "__future__":
            if not self.futuresAllowed:
                self.report(
                    messages.LateFutureImport,
                    node,
                    [n.name for n in node.names],
                )
        else:
            self.futuresAllowed = False

        module = ("." * node.level) + (node.module or "")

        for alias in node.names:
            name = alias.asname or alias.name
            if node.module == "__future__":
                importation = FutureImportation(name, node, self.scope)
                if alias.name == "annotations":
                    self.annotationsFutureEnabled = True
            elif alias.name == "*":
                self.scope.importStarred = True
                self.report(messages.ImportStarUsed, node, module)
                importation = StarImportation(module, node)
            else:
                importation = ImportationFrom(name, node, module, alias.name)
            self.addBinding(node, importation)

    def TRY(self, node):
        handler_names = []
        # List the exception handlers
        for i, handler in enumerate(node.handlers):
            if isinstance(handler.type, ast.Tuple):
                for exc_type in handler.type.elts:
                    handler_names.append(getNodeName(exc_type))
            elif handler.type:
                handler_names.append(getNodeName(handler.type))

            if handler.type is None and i < len(node.handlers) - 1:
                self.report(messages.DefaultExceptNotLast, handler)
        # Memorize the except handlers and process the body
        self.exceptHandlers.append(handler_names)
        for child in node.body:
            self.handleNode(child, node)
        self.exceptHandlers.pop()
        # Process the other nodes: "except:", "else:", "finally:"
        self.handleChildren(node, omit="body")

    TRYEXCEPT = TRY

    def EXCEPTHANDLER(self, node):
        if node.name is None:
            self.handleChildren(node)
            return

        # If the name already exists in the scope, modify state of existing
        # binding.
        if node.name in self.scope:
            self.handleNodeStore(node)

        try:
            prev_definition = self.scope.pop(node.name)
        except KeyError:
            prev_definition = None

        self.handleNodeStore(node)
        self.handleChildren(node)

        # See discussion on https://github.com/PyCQA/pyflakes/pull/59

        # We're removing the local name since it's being unbound after leaving
        # the except: block and it's always unbound if the except: block is
        # never entered. This will cause an "undefined name" error raised if
        # the checked code tries to use the name afterwards.
        #
        # Unless it's been removed already. Then do nothing.

        try:
            binding = self.scope.pop(node.name)
        except KeyError:
            pass
        else:
            if not binding.used:
                self.report(messages.UnusedVariable, node, node.name)

        # Restore.
        if prev_definition:
            self.scope[node.name] = prev_definition

    def ANNASSIGN(self, node):
        if node.value:
            # Only bind the *targets* if the assignment has a value.
            # Otherwise it's not really ast.Store and shouldn't silence
            # UndefinedLocal warnings.
            self.handleNode(node.target, node)
        self.handleAnnotation(node.annotation, node)
        if node.value:
            # If the assignment has value, handle the *value* now.
            self.handleNode(node.value, node)

    def COMPARE(self, node):
        self.handleChildren(node)
