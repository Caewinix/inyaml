from typing import Callable, Any, Dict
import inspect
import yaml
from numba import jit

@jit(nopython=True)
def find_mark(buffer: str):
    char_list = [':', ',', ']', '}', ')']
    for i, char in enumerate(buffer):
        if char in char_list:
            return i
    return -1

def end_mark(node: yaml.ScalarNode):
    return node.end_mark.buffer[node.end_mark.index]

def is_real_str_value(node: yaml.ScalarNode):
    if node.style is None:
        buffer = node.end_mark.buffer[node.start_mark.index:]
        mark_index = find_mark(buffer)
        if mark_index != -1:
            substring_before_mark = buffer[:mark_index]
            if not '!!str' in substring_before_mark:
                return False
    return True

def construct_yaml_str(loader: yaml.Loader, node: yaml.ScalarNode, globals=None, locals=None):
    value = loader.construct_scalar(node)
    if end_mark(node) != ':':
        if not is_real_str_value(node):
            value = eval(value, globals, locals)
    return value

# def construct_yaml_str(loader: yaml.Loader, node: yaml.ScalarNode):
#     value = loader.construct_scalar(node)
#     if node.end_mark.buffer[node.end_mark.index] != ':':
#         if node.style is None:
#             buffer = node.end_mark.buffer[node.start_mark.index:]
#             mark_index = find_mark(buffer)
#             if mark_index != -1:
#                 substring_before_mark = buffer[:mark_index]
#                 if not '!!str' in substring_before_mark:
#                     value = eval(value)
#     return value

def construct_yaml_seq(loader: yaml.Loader, node: yaml.SequenceNode):
    data = []
    yield data
    data.extend(construct_sequence(loader, node))

def construct_sequence(loader: yaml.Loader, node: yaml.SequenceNode, deep=False):
    if not isinstance(node, yaml.SequenceNode):
        raise yaml.constructor.ConstructorError(None, None,
                "expected a sequence node, but found %s" % node.id,
                node.start_mark)
    return [construct_object(loader, child, deep=deep) for child in node.value]

def construct_object(loader: yaml.Loader, node: yaml.SequenceNode, deep=False):
    string_tag = 'tag:yaml.org,2002:str'
    if node.tag == string_tag:
        return loader.__class__.yaml_constructors[string_tag](loader, node)
    else:
        return loader.construct_object(node, deep=deep)

def back_locals() -> Dict:
    return inspect.currentframe().f_back.f_back.f_locals

# def import_target(path: str, need_target = True):
#     last_point_index = path.rfind('.')
#     if last_point_index == -1:
#         to_be_imported = path
#     else:
#         to_be_imported = path[last_point_index + 1:]
#         path = 'from ' + path[:last_point_index] + ' import ' + to_be_imported
#         eval(path)
#     if need_target:
#         return eval(to_be_imported)