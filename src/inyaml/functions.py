from typing import Iterable, Any
import os
from .utils.var import back_locals, back_globals
from .utils.yaml_import_renames import get_import_renames
from .namespace import Dictspace
from . import special_keys


def load(
    stream,
    is_instantiable: bool = True,
    variables: dict[str, Any] = dict(),
    avoidance: Iterable[Any] = [os],
    *,
    run_id = special_keys.run_id,
    import_id = special_keys.import_id,
    imported_targets_id = special_keys.imported_targets_id,
    args_id = special_keys.args_id,
    kwargs_id = special_keys.kwargs_id,
):
    """
    Parse the first YAML document in a stream
    and produce the corresponding Python object.
    """
    if is_instantiable:
        from .instantiable_construction import InstantiableLoader
        loader = InstantiableLoader(stream, avoidance, args_id, kwargs_id, run_id, import_id, imported_targets_id)
    else:
        from .executable_construction import ExecutableLoader
        loader = ExecutableLoader(stream, avoidance, run_id, import_id, imported_targets_id)
    loader.__package__ = __package__
    loader.__vars__.update(variables)
    loader.__vars__.update(back_globals())
    loader.__vars__.update(back_locals())
    try:
        data = loader.get_single_data()
        if len(loader.__import__) > 0:
            super(dict, data).__setattr__(loader.__imported_targets_id__, Dictspace(loader.__import__))
        return data
    finally:
        loader.dispose()


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