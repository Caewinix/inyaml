from lark import Transformer, Lark

parser = Lark(
r"""
?value: list | name

!name: NAME
NAME: /[^\W\d]\w*/
list : "(" [value ("," value)*] ")"

%import common.WS
%ignore WS
""", start='value')


class YAMLImportRenamesTransformer(Transformer):
    def name(self, value):
        return str(value[0])
    list = list


def get_import_renames(text):
    tree = parser.parse(text)
    return YAMLImportRenamesTransformer().transform(tree)