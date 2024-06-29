import collections.abc, types
import copy
import re
import yaml.composer
import yaml.parser
import yaml.scanner
from . import const_id
from .namespace import Namespace
from .executable_construction import ExecutableConstructor

def extract_arguments(*args, **kwargs):
    return args, kwargs

def is_custom_type_node(node: yaml.Node):
    # If the type is not a custom type but a YAML type, its tag will
    # start with 'tag:yaml.org,2002:', even if the prefix '!!' is specified.
    return node.tag.startswith('!')

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
        args_id = const_id.args_id,
        kwargs_id = const_id.kwargs_id,
        run_id = const_id.run_id,
        import_id = const_id.import_id,
        imported_targets_id = const_id.imported_targets_id
    ):
        super().__init__(run_id, import_id, imported_targets_id)
        self.__args_id__ = args_id
        self.__kwargs_id__ = kwargs_id
    
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
        instance_type: str = node.tag[1:]
        target_names = instance_type.split('.')
        target = self.__vars__.get(target_names[0])
        if target is None:
            target = self.import_target(instance_type)
        else:
            target_names = target_names[1:]
            for target_name in target_names:
                target = getattr(target, target_name)
        args, kwargs = self.construct_arguments(node)
        return target(*args, **kwargs)
    
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
        # Create mapping without delay.
        mapping = {}
        for key_node, value_node in node.value:
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
        if is_custom_type_node(node):
            return self.construct_object(node, deep)
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
                key = self.construct_object(key_node, deep=deep)
                if not isinstance(key, collections.abc.Hashable):
                    raise yaml.constructor.ConstructorError("While constructing a mapping", node.start_mark,
                            "found unhashable key", key_node.start_mark)
                if key == self.__args_id__:
                    args += self.construct_instantiating_sequence(value_node, deep)
                elif key == self.__kwargs_id__:
                    kwargs.update(self.construct_instantiating_mapping(value_node, deep))
                else:
                    if isinstance(value_node, yaml.MappingNode):
                        raise yaml.constructor.ConstructorError("A `dict` passed as an argument should be wrapped in the `[]`.", value_node.end_mark)
                    pair = self.import_target_from_node(node, key_node, value_node, deep)
                    if pair is None:
                        key = self.escape_special_key(key, self.__import_id__)
                    else:
                        key, _ = pair
                    key = self.escape_special_key(key, self.__args_id__)
                    key = self.escape_special_key(key, self.__kwargs_id__)
                    self.check_key_format(key, key_node)
                    instantiating_value = self.construct_instantiating_value(value_node, deep=deep)
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
                        new_args, new_kwargs = eval(f'extract_arguments{value_scalar[1:]}')
                        args += new_args
                        kwargs.update(new_kwargs)
                        return args, kwargs
                    # else:
                    #     '''
                    #     instance: !type "the only arg"
                    #     '''
                    #     value = eval(value_scalar)
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
    
    def construct_object(self, node, deep=False):
        if node in self.constructed_objects:
            return self.constructed_objects[node]
        if deep:
            old_deep = self.deep_construct
            self.deep_construct = True
        if node in self.recursive_objects:
            raise yaml.constructor.ConstructorError(None, None,
                    "found unconstructable recursive node", node.start_mark)
        self.recursive_objects[node] = None
        constructor = None
        tag_suffix = None
        if node.tag in self.yaml_constructors:
            constructor = self.yaml_constructors[node.tag]
        elif is_custom_type_node(node): # The only modification in this method.
            constructor = self.__class__.construct_yaml_instance
        else:
            for tag_prefix in self.yaml_multi_constructors:
                if tag_prefix is not None and node.tag.startswith(tag_prefix):
                    tag_suffix = node.tag[len(tag_prefix):]
                    constructor = self.yaml_multi_constructors[tag_prefix]
                    break
            else:
                if None in self.yaml_multi_constructors:
                    tag_suffix = node.tag
                    constructor = self.yaml_multi_constructors[None]
                elif None in self.yaml_constructors:
                    constructor = self.yaml_constructors[None]
                elif isinstance(node, yaml.ScalarNode):
                    constructor = self.__class__.construct_scalar
                elif isinstance(node, yaml.SequenceNode):
                    constructor = self.__class__.construct_sequence
                elif isinstance(node, yaml.MappingNode):
                    constructor = self.__class__.construct_mapping
        if tag_suffix is None:
            data = constructor(self, node)
        else:
            data = constructor(self, tag_suffix, node)
        if isinstance(data, types.GeneratorType):
            generator = data
            data = next(generator)
            if self.deep_construct:
                for dummy in generator:
                    pass
            else:
                self.state_generators.append(generator)
        self.constructed_objects[node] = data
        del self.recursive_objects[node]
        if deep:
            self.deep_construct = old_deep
        return data

InstantiableConstructor.add_constructor('tag:yaml.org,2002:namespace', InstantiableConstructor.construct_yaml_namespace)

class InstantiableLoader(yaml.reader.Reader, yaml.scanner.Scanner, yaml.parser.Parser, yaml.composer.Composer, InstantiableConstructor, yaml.resolver.Resolver):
    def __init__(
        self,
        stream,
        args_id = const_id.args_id,
        kwargs_id = const_id.kwargs_id,
        run_id = const_id.run_id,
        import_id = const_id.import_id,
        imported_targets_id = const_id.imported_targets_id
    ):
        yaml.reader.Reader.__init__(self, stream)
        yaml.scanner.Scanner.__init__(self)
        yaml.parser.Parser.__init__(self)
        yaml.composer.Composer.__init__(self)
        InstantiableConstructor.__init__(self, args_id, kwargs_id, run_id, import_id, imported_targets_id)
        yaml.resolver.Resolver.__init__(self)