from typing import Any


class Dictspace(dict):
    """
    Simple object for storing attributes.

    Implements equality by attribute names and values, and provides a simple
    string representation.
    """
    def __getitem__(self, name):
        return self.get(name)
    
    def __getattr__(self, name):
        return self[name]
    
    def __setattr__(self, name: str, value: Any):
        self[name] = value
    
    def __delattr__(self, name: str):
        del self[name]

    def __eq__(self, other):
        if not isinstance(other, Dictspace):
            return NotImplemented
        return vars(self) == vars(other)

    def __contains__(self, key):
        return key in self


class Namespace(Dictspace):
    def __repr__(self):
        arg_strings = []
        star_args = {}
        for arg in self.__get_args():
            arg_strings.append(repr(arg))
        for name, value in self.__get_kwargs():
            if name.isidentifier():
                arg_strings.append('%s=%r' % (name, value))
            else:
                star_args[name] = value
        if star_args:
            arg_strings.append('**%s' % repr(star_args))
        return '{%s}' % (', '.join(arg_strings))

    def __get_kwargs(self):
        return list(self.items())

    def __get_args(self):
        return []