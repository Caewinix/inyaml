import collections.abc
import os
import importlib
from typing import Optional, Dict, Sequence
import yaml
import yaml.composer
import yaml.parser
import yaml.scanner
from .parser import Parser
from .composer import Composer
from . import special_keys
from .functions import get_import_renames, flatten_list
from .utils.restricted_parse import avoidance_eval


def exec_locals(path: str):
    '''
    Return the local variables after executaing any commands.
    '''
    exec(path)
    return locals()


class ExecutableConstructor(yaml.constructor.SafeConstructor):
    '''
    Distinguish whether the current value is a string or an executable Python code
    by whether there is wrapped by `""` or `''`. If the code is executable, the
    return value will be assigned to the current key. In addition, the key import and
    key run functions can also be used, which will not store the execution results.
    
    Moreover, modules or classes can be renamed by simply using '(name_1, name_2, ...)'
    at the end of the key import, which means that the imported packages or classes can
    be accessed with a new name in another location.
    '''
    def __init__(
        self,
        avoidance = [os],
        run_id = special_keys.run_id,
        import_id = special_keys.import_id,
        imported_targets_id = special_keys.imported_targets_id
    ):
        super().__init__()
        self.avoidance = avoidance
        self.__run_id__ = run_id
        self.__import_id__ = import_id
        self.__package__: Optional[str] = None
        self.__vars__ = {}
        self.__import__ = {}
        self.__imported_targets_id__ = imported_targets_id
    
    def construct_yaml_str(self, node):
        value = super().construct_yaml_str(node)
        if node.style is None and not (getattr(node, 'is_key', False) or getattr(node, 'has_str_tag', False)):
            return avoidance_eval(value, None, self.__vars__, avoidance=self.avoidance)
        return value
    
    def import_target(self, path: str, returns_dict=False):
        last_point_index = path.rfind('.')
        if last_point_index != -1:
            target = path[last_point_index + 1:]
            if target == '*':
                final_dict = exec_locals(f'from {path[:last_point_index]} import *')
            else:
                final_dict = []
                type_infos = path.split('.')
                length = len(type_infos) - 2
                i = -1
                for i in range(length):
                    try:
                        module = importlib.import_module('.'.join(type_infos[:-(i + 1)]))
                        break
                    except ModuleNotFoundError: ...
                else:
                    i += 1
                    module = importlib.import_module('.'.join(type_infos[:-(i + 1)]))
                for name in type_infos[-(i + 1):-1]:
                    module = getattr(module, name)
                targets = type_infos[-1].split(',')
                for target in targets:
                    name = target.strip()
                    target = getattr(module, name)
                    final_dict.append({name : target})
        else:
            while True:
                try:
                    name = path
                    target = avoidance_eval(name, None, self.__vars__, avoidance=self.avoidance)
                    final_dict = [{name : target}]
                    break
                except NameError:
                    self.__vars__.update(exec_locals(f'import {name}'))
                except:
                    raise # yaml.constructor.ConstructorError(f"No such module or member named as `{name}`") from None
        if returns_dict:
            return final_dict
        else:
            return target
    
    def escape_special_key(self, key, special_key):
        return key
    
    def check_key_format(self, key, key_node):
        pass
    
    def construct_value(self, parent_node, node, deep=False):
        return self.construct_object(node, deep)
    
    def construct_object(self, node, deep=False):
        data = super().construct_object(node, deep)
        return data
    
    def dictionary_pair(self, node, key_node: yaml.Node, value_node: yaml.Node, deep=False):
        key = self.construct_object(key_node, deep=deep)
        if not isinstance(key, collections.abc.Hashable):
            raise yaml.constructor.ConstructorError("while constructing a mapping", node.start_mark,
                    "found unhashable key", key_node.start_mark)
        import_id_length = len(self.__import_id__)
        if key[:import_id_length] == self.__import_id__:
            if value_node.style is not None:
                raise yaml.constructor.ConstructorError("The import value should not be a `str`, which is wrapped in `\"\"` or `''`.", value_node.start_mark)
            path = self.construct_scalar(value_node)
            final_dict = self.import_target(path, True)
            vars_dict = {}
            if len(key) > import_id_length:
                if isinstance(final_dict, Dict):
                    raise yaml.constructor.ConstructorError(
                        "Renames of imported targets cannot be used when importing all from a module.",
                        key_node.start_mark)
                as_names = get_import_renames(key[import_id_length:].strip())
                assert len(as_names) == len(final_dict), 'Renames are not matched with imported targets.'
                for as_name, pair in zip(as_names, final_dict):
                    if isinstance(as_name, Sequence):
                        as_name = flatten_list(as_name)
                        for name in as_name:
                            for _, target in pair.items():
                                vars_dict.update({name : target})
                    else:
                        for _, target in pair.items():
                            vars_dict.update({as_name : target})
            else:
                if isinstance(final_dict, Dict):
                    vars_dict = final_dict
                else:
                    for pair in final_dict:
                        for name, target in pair.items():
                            vars_dict.update({name : target})
            self.__import__.update(vars_dict)
            self.__vars__.update(vars_dict)
        else:
            key = self.escape_special_key(key, self.__import_id__)
            self.check_key_format(key, key_node)
            value = self.construct_value(node, value_node, deep=deep)
            return key, value
    
    def construct_mapping(self, node, deep=False):
        if isinstance(node, yaml.MappingNode):
            self.flatten_mapping(node)
        else:
            raise yaml.constructor.ConstructorError(None, None,
                    "expected a mapping node, but found %s" % node.id,
                    node.start_mark)
        mapping = {}
        for key_node, value_node in node.value:
            key_node.is_key = True
            pair = self.dictionary_pair(node, key_node, value_node, deep)
            if pair is not None:
                key, value = pair
                if key != self.__run_id__:
                    mapping[key] = value
        return mapping


ExecutableConstructor.add_constructor('tag:yaml.org,2002:str', ExecutableConstructor.construct_yaml_str)


class ExecutableLoader(yaml.reader.Reader, yaml.scanner.Scanner, Parser, Composer, ExecutableConstructor, yaml.resolver.Resolver):
    def __init__(
        self,
        stream,
        avoidance = [os],
        run_id = special_keys.run_id,
        import_id = special_keys.import_id,
        imported_targets_id = special_keys.imported_targets_id
    ):
        yaml.reader.Reader.__init__(self, stream)
        yaml.scanner.Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        ExecutableConstructor.__init__(self, avoidance, run_id, import_id, imported_targets_id)
        yaml.resolver.Resolver.__init__(self)