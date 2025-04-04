# InYAML

## Overview
The library based on `PyYAML` promises to parse YAML documents and produce Python objects, for executing Python code within YAML documents and instantiating Python objects based on YAML arguments.

## Features
- **Executable YAML**: This introduces Python code defined within YAML documents when the code is not wrapped in the `""` or `''`. It supports importing modules, executing arbitrary Python expressions directly from YAML.
- **Instantiable YAML**: It is not only `Executable` but also supports instantiating Python objects as defined by class or function tags in YAML. This allows the YAML to not just carry data but also semantic information about how the data should be instantiated into Python objects.
- **Dynamic Import and Execution**: Functionality to dynamically import Python modules and execute functions as specified in the YAML, providing flexibility and powerful integration capabilities.

## Key Components
**`ExecutableConstructor`**:
  - Executes Python codes or expressions within YAML.
  - Manages import (`__import__` as the default key) and run (`__run__` as the default key) executions through special YAML keys.
  - Ensures that only designated code is executed.

**`InstantiableConstructor`**:
  - Inherits from `ExecutableConstructor`.
  - Adds the capability to instantiate objects using type specifications provided in YAML tags.
  - Supports advanced features like namespace and argument passing for constructors.

**`load` Function**:
  - Parses YAML documents and uses either `ExecutableConstructor` or `InstantiableConstructor` based on whether the `is_instantiable` is `True` or not.
  - All imported modules or classes will be stores in the imported targets attribute (`__import__` as the default identifier) of the outermost `Namespace`.

## Installation
```
pip install inyaml
```

## Usage Example

```python
import inyaml

class TestClass:
    def __init__(self, *args, **kwargs):
        print(args)
        print(kwargs)
        print('TestClass')

def test_run_function(arg=0):
    print(arg)

input_data = """
add: 1+2
string: "string"
number: 3
outer_namespace: &ref
 inner_namespace:
  first: [9+ 8,{'any_number':99}]
  second: {"any_number":333}
list: [{'any_float':99.1}, 1, 2, 3+4, *ref]
__import__ (np): numpy
dict: {"any_number_in_a_dict":444}
__run__: test_run_function()
instance: !TestClass
 string: "from"
 __args__: [1,2,3]
 __kwargs__:
  first: 1
  second: 2
 number: 12345
 np_array: &ref_2 !np.array ~([1, 20, 300])
 np_array_2: !np.array [[1, 20, 300]]
 np_array_3: *ref_2
 __run__: test_run_function(25)
"""

print(inyaml.load(input_data))
```

## Safety Notice
While this library allows execution of Python code specified in YAML, it should be used with caution to avoid executing untrusted code, especially in applications where YAML documents could come from untrusted sources.

Although it has been processed to avoid many dangerous situations, it is possible to introduce dangerous code when setting types and functions using `![any]`. Please ensure that all introduced types and functions are safe.