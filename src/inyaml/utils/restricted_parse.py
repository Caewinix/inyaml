from typing import Optional, Any, Dict, Iterable, Mapping
import ast
import os
import inspect
from RestrictedPython import compile_restricted
from RestrictedPython.Guards import safe_builtins
from RestrictedPython.Eval import default_guarded_getiter
from RestrictedPython.Guards import guarded_iter_unpack_sequence, safer_getattr
from typing import Mapping
from copy import copy


global_dict = {
    '__name__': '__main__',
    '__metaclass__': type,
    '_getiter_': default_guarded_getiter,
    '_iter_unpack_sequence_': guarded_iter_unpack_sequence,
    '_getattr_': safer_getattr,
    '__builtins__': safe_builtins,
}


# def restricted_exec(
#     source,
#     globals: Optional[Dict[str, Any]] = None,
#     locals: Optional[Mapping[str, object]] = None,
#     admission: Optional[Iterable[object]] = [],
#     avoidance: Optional[Iterable[object]] = None
# ):
#     compiled_code = compile_restricted(source, '<string>', 'exec')
#     if admission is not None:
#         def restricted_import(
#             name: str,
#             globals: Optional[Dict[str, Any]] = None,
#             locals: Optional[Mapping[str, object]] = None,
#             fromlist: Sequence[str] = (),
#             level: int = 0,
#         ):
#             imported = __import__(name, globals, locals, fromlist, level)
#             can_be_imported = True
#             for obj in admission:
#                 can_be_imported = can_be_imported and ((obj.__name__ in name and obj is imported) or (obj.__name__ in fromlist and hasattr(imported, obj.__name__)))
#             length = len(fromlist)
#             if length == 0:
#                 raise ImportError(f"'{name}' is not allowed to be imported in this context.")
#             else:
#                 fromstr = f"'{fromlist[0]}'"
#                 if length > 1:
#                     for i, frompart in enumerate(fromlist[1:]):
#                         if i == length - 2:
#                             fromstr += f" and '{frompart}'"
#                         else:
#                             fromstr += f", '{frompart}'"
#                 raise ImportError(f"{fromstr} in the module '{name}' is not allowed to be imported in this context.")
#         import_func = restricted_import
#     else:
#         import_func = __import__
#     if avoidance is not None:
#         def restricted_import(
#             name: str,
#             globals: Optional[Dict[str, Any]] = None,
#             locals: Optional[Mapping[str, object]] = None,
#             fromlist: Sequence[str] = (),
#             level: int = 0,
#         ):
#             imported = __import__(name, globals, locals, fromlist, level)
#             for obj in admission:
#                 if (obj.__name__ in name and obj is imported) or (obj.__name__ in fromlist and hasattr(imported, obj.__name__)):
#                     raise 
#     exec_global_dict = copy(global_dict)
#     exec_global_dict.update({})
#     exec(compiled_code, globals, locals)


def restricted_eval(source, globals: Optional[Dict[str, Any]] = None, locals: Optional[Mapping[str, object]] = None):
    compiled_code = compile_restricted(source, '<string>', 'eval')
    if globals is not None:
        globals = copy(globals)
        globals.update(global_dict)
    return eval(compiled_code, globals, locals)


def check_avoidance(variable, avoidance, name = ''):
    for avoiding_variable in avoidance:
        try:
            is_in_avoidance = (variable is getattr(avoiding_variable, variable.__name__, None))
        except AttributeError:
            is_in_avoidance = False
        if (
            (inspect.ismodule(avoiding_variable) and is_in_avoidance) or
            (isinstance(avoiding_variable, type) and (issubclass(variable, avoiding_variable) or isinstance(variable, avoiding_variable) or is_in_avoidance)) or
            (variable is avoiding_variable)
        ):
            raise RuntimeError(f"'{name} ({variable})' is forbidden in this context")


class AvoidanceVisitor(ast.NodeVisitor):
    def __init__(self, avoidance = [], globals = None, locals = None):
        super().__init__()
        self.avoidance = avoidance
        self.globals = globals
        self.locals = locals
    
    def visit_Name(self, node: ast.Name):
        name = node.id
        variable = eval(name, self.globals, self.locals)
        check_avoidance(variable, self.avoidance, name)
        self.generic_visit(node)


def avoidance_eval(
    source: str,
    globals: Optional[Dict[str, Any]] = None,
    locals: Optional[Mapping[str, object]] = None,
    avoidance: Iterable[Any] = [os]
):
    tree = ast.parse(source, mode='eval')
    last_globals = inspect.currentframe().f_back.f_globals
    last_locals = inspect.currentframe().f_back.f_locals
    if globals is None:
        globals = {}
    if locals is None:
        locals = {}
    globals.update(last_globals)
    locals.update(last_locals)
    visitor = AvoidanceVisitor(avoidance, globals, locals)
    visitor.visit(tree)
    return restricted_eval(source, globals, locals)