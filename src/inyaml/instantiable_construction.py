import collections.abc
import inspect
import os
import copy
import re
import yaml.composer
import yaml.parser
import yaml.scanner
from .parser import Parser
from .composer import Composer
from . import special_keys
from .namespace import Namespace
from .executable_construction import ExecutableConstructor
from .utils.restricted_parse import avoidance_eval, check_avoidance


class TagOnlyError(Exception): ...


def extract_arguments(*args, **kwargs):
    return args, kwargs


class DelayConstructor:
    def __init__(self, target, *arguments, **keyword_arguments):
        self.target = target
        self.arguments = arguments
        self.keyword_arguments = keyword_arguments
    
    @property
    def __signature__(self):
        return inspect.signature(self.target)
    
    def __call__(self, *args, **kwargs):
        arguments = self.__signature__.bind_partial(*args, *self.arguments, **kwargs, **self.keyword_arguments).arguments
        
        for name, value in arguments.items():
            if isinstance(value, ChainedDelayConstructor):
                arguments[name] = value(*args, **kwargs)
        
        return self.target(**arguments)


class ChainedDelayConstructor(DelayConstructor):
    ...


class InstantiableConstructor(ExecutableConstructor):
    '''
    This constructor not only executes codes based on `ExecutableConstructor` but
    also can instantiate objects when specifying the type after the mark `!`. All
    YAML attributed dictionary can also be regared as an object, which is a
    namespace in this constructor, which means they can be accessed by not only
    `[] (__getitem__)` but also dot operator (__getattr__), all not existed attribute
    will result in a `None` return.
    '''
    def __init__(
        self,
        avoidance = [os],
        args_id = special_keys.args_id,
        kwargs_id = special_keys.kwargs_id,
        run_id = special_keys.run_id,
        import_id = special_keys.import_id,
        imported_targets_id = special_keys.imported_targets_id
    ):
        super().__init__(avoidance, run_id, import_id, imported_targets_id)
        self.__args_id__ = args_id
        self.__kwargs_id__ = kwargs_id
    
    def is_custom_type_node(self, node: yaml.Node):
        # If the type is not a custom type but a YAML type, its tag will
        # start with 'tag:yaml.org,2002:', even if the prefix '!!' is specified.
        if node.tag == 'tag:yaml.org,2002:instance':
            return True
        result = node.tag.startswith('!') and node.tag not in self.yaml_constructors
        for tag_prefix in self.yaml_multi_constructors:
            result = result and (tag_prefix is None or not node.tag.startswith(tag_prefix))
            if not result:
                break
        return result
    
    def construct_document(self, node):
        # Make the final top element `Namespace`.
        data = super().construct_document(node)
        if isinstance(data, dict):
            data = Namespace(data)
        return data
    
    def construct_value(self, parent_node, node, deep=False):
        if isinstance(parent_node, yaml.MappingNode) and node.tag == 'tag:yaml.org,2002:map' and (not node.flow_style):
            node.tag = 'tag:yaml.org,2002:namespace'
        return self.construct_object(node, deep)

    def construct_yaml_namespace(self, node):
        data = Namespace()
        yield data
        value = self.construct_mapping(node)
        data.update(value)
    
    def construct_yaml_instance(self, node: yaml.Node):
        instance_type: str = node.type
        target_names = instance_type.split('.')
        target_name = target_names[0]
        target = self.__vars__.get(target_name)
        if target is None:
            target = self.import_target(instance_type)
        else:
            target_names = target_names[1:]
            for target_name in target_names:
                target = getattr(target, target_name)
        check_avoidance(target, self.avoidance, target_name)
        try:
            args, kwargs = self.construct_arguments(node)
            if getattr(node, 'is_incomplete', False):
                return DelayConstructor(target, *args, **kwargs)
            elif getattr(node, 'is_incomplete_chain', False):
                return ChainedDelayConstructor(target, *args, **kwargs)
            else:
                return target(*args, **kwargs)
        except TagOnlyError:
            return target
    
    def escape_special_key(self, key, special_key):
        # Make the special key, like `__import_id__` key, as a key but remove the
        # special meanings.
        if key[:len(special_key) + 1] == f'\\{special_key}':
            key = key[1:]
        return key
    
    def check_key_format(self, key, key_node):
        # Ensure that the key is Pythonicly named.
        if re.fullmatch(r'[^\W\d]\w*', key) is None:
            raise yaml.constructor.ConstructorError(
                "The identifier of the key should comply with Python naming conventions.",
                key_node.start_mark)
    
    def construct_instantiating_mapping(self, node: yaml.MappingNode, deep=False):
        # Create mapping without a delay.
        mapping = {}
        for key_node, value_node in node.value:
            key_node.is_key = True
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, collections.abc.Hashable):
                raise yaml.constructor.ConstructorError("while constructing a mapping", node.start_mark,
                        "found unhashable key", key_node.start_mark)
            value = self.construct_instantiating_value(value_node, deep=deep)
            mapping[key] = value
        return mapping
    
    def construct_instantiating_sequence(self, node: yaml.SequenceNode, deep=False):
        # Create sequence without delay.
        return [self.construct_instantiating_value(child, deep=deep) for child in node.value]

    def construct_instantiating_value(self, node, deep=False):
        if self.make_instance_tag(node):
            return super().construct_object(node, deep)
        else:
            # Ensure all variables will be initialized without using `yield`.
            if isinstance(node, yaml.MappingNode):
                return self.construct_instantiating_mapping(node, deep)
            elif isinstance(node, yaml.SequenceNode):
                return self.construct_instantiating_sequence(node, deep)
            else:
                return self.construct_object(node, deep)
    
    def construct_arguments(self, node: yaml.Node, deep=False):
        # Construct the arguments that is necessary to be passed into the `__init__`.
        args, kwargs = [], {}
        if isinstance(node, yaml.MappingNode):
            '''
            instance: !type
                __args__: [1, 2, 3]
                __kwargs__:
                    first: "1st"
                    second: '2nd'
            '''
            self.flatten_mapping(node)
            for key_node, value_node in node.value:
                key_node.is_key = True
                key = self.construct_object(key_node, deep=deep)
                if not isinstance(key, collections.abc.Hashable):
                    raise yaml.constructor.ConstructorError("While constructing a mapping", node.start_mark,
                            "found unhashable key", key_node.start_mark)
                if key == self.__args_id__:
                    args += self.construct_instantiating_sequence(value_node, deep)
                elif key == self.__kwargs_id__:
                    kwargs.update(self.construct_instantiating_mapping(value_node, deep))
                else:
                    if not self.is_custom_type_node(value_node) and isinstance(value_node, yaml.MappingNode):
                        raise yaml.constructor.ConstructorError("A `dict` passed as an argument should be wrapped in the `[]`.", value_node.end_mark)
                    instantiating_value = self.construct_instantiating_value(value_node, deep=deep)
                    pair = self.dictionary_pair(node, key_node, value_node, deep)
                    if pair is None:
                        key = self.escape_special_key(key, self.__import_id__)
                    else:
                        key, _ = pair
                    key = self.escape_special_key(key, self.__args_id__)
                    key = self.escape_special_key(key, self.__kwargs_id__)
                    self.check_key_format(key, key_node)
                    if key != self.__run_id__:
                        kwargs.update({key : instantiating_value})
        else:
            value_scalar = node.value
            value_node = copy.deepcopy(node)
            if isinstance(value_node, yaml.ScalarNode):
                if value_node.style is None:
                    if value_scalar.startswith('~(') and value_scalar.endswith(')'):
                        '''
                        instance: !type ~(1, 2, 3, first="1st", second='2nd')
                        '''
                        new_args, new_kwargs = avoidance_eval(f'{extract_arguments.__code__.co_name}{value_scalar[1:]}', avoidance=self.avoidance)
                        args += new_args
                        kwargs.update(new_kwargs)
                        return args, kwargs
                    elif value_scalar == '':
                        raise TagOnlyError()
                    # else:
                    #     '''
                    #     instance: !type "the only arg"
                    #     '''
                    #     value = safeeval(value_scalar, avoidance=self.avoidance)
                else:
                    value = value_scalar
                args.append(value)
            # elif isinstance(value_node, yaml.MappingNode):
            #     '''
            #     instance: !type {'first': "1st", 'second': '2nd'}
            #     '''
            #     value = self.construct_mapping_directly(value_node, deep)
            elif isinstance(value_node, yaml.SequenceNode):
                '''
                instance: !type [1, 2, 3]
                '''
                values = self.construct_instantiating_sequence(value_node, deep)
                args += values
        return args, kwargs
    
    def make_instance_tag(self, node):
        if self.is_custom_type_node(node):
            if node.tag[1] == '?':
                if node.tag[2] == '*':
                    node.is_incomplete_chain = True
                    node.type = node.tag[3:]
                else:
                    node.is_incomplete = True
                    node.type = node.tag[2:]
            else:
                node.type = node.tag[1:]
            node.tag = 'tag:yaml.org,2002:instance'
            return True
        return False
    
    def construct_object(self, node, deep=False):
        self.make_instance_tag(node)
        return super().construct_object(node, deep)


InstantiableConstructor.add_constructor('tag:yaml.org,2002:namespace', InstantiableConstructor.construct_yaml_namespace)
InstantiableConstructor.add_constructor('tag:yaml.org,2002:instance', InstantiableConstructor.construct_yaml_instance)


class InstantiableLoader(yaml.reader.Reader, yaml.scanner.Scanner, Parser, Composer, InstantiableConstructor, yaml.resolver.Resolver):
    def __init__(
        self,
        stream,
        avoidance = [os],
        args_id = special_keys.args_id,
        kwargs_id = special_keys.kwargs_id,
        run_id = special_keys.run_id,
        import_id = special_keys.import_id,
        imported_targets_id = special_keys.imported_targets_id
    ):
        yaml.reader.Reader.__init__(self, stream)
        yaml.scanner.Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        InstantiableConstructor.__init__(self, avoidance, args_id, kwargs_id, run_id, import_id, imported_targets_id)
        yaml.resolver.Resolver.__init__(self)