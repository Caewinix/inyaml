import yaml
from .construction import construct_yaml_str, construct_yaml_seq, back_locals
from .yaml_import_renames import get_import_renames
from .namespace import Dictspace
from . import const_id

def load(
    stream,
    is_instantiable: bool = True,
    *,
    run_id = const_id.run_id,
    import_id = const_id.import_id,
    imported_targets_id = const_id.imported_targets_id,
    args_id = const_id.args_id,
    kwargs_id = const_id.kwargs_id,
):
    """
    Parse the first YAML document in a stream
    and produce the corresponding Python object.
    """
    if is_instantiable:
        from .instantiable_construction import InstantiableLoader
        loader = InstantiableLoader(stream, args_id, kwargs_id, run_id, import_id, imported_targets_id)
    else:
        from .executable_construction import ExecutableLoader
        loader = ExecutableLoader(stream, run_id, import_id, imported_targets_id)
    loader.__package__ = __package__
    loader.__vars__.update(back_locals())
    try:
        data = loader.get_single_data()
        if len(loader.__import__) > 0:
            setattr(data, loader.__imported_targets_id__, Dictspace(loader.__import__))
        return data
    finally:
        loader.dispose()


def execute_constructor(constructor: yaml.constructor.Constructor):
    constructor.add_constructor('tag:yaml.org,2002:str', construct_yaml_str)
    constructor.add_constructor('tag:yaml.org,2002:seq', construct_yaml_seq)


def flatten_list(nested_list):
    stack = [nested_list]
    flat_list = []
    while stack:
        current = stack.pop()
        if isinstance(current, list):
            for item in reversed(current):
                stack.append(item)
        else:
            flat_list.append(current)
    return flat_list