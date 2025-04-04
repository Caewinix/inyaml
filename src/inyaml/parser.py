import yaml


class Parser(yaml.parser.Parser):
    def parse_node(self, block=False, indentless_sequence=False):
        token = self.peek_token()
        event = super().parse_node(block, indentless_sequence)
        if isinstance(event, yaml.ScalarEvent) and isinstance(token, yaml.TagToken):
            tag = token.value
            handle, suffix = tag
            if handle is not None and handle in self.tag_handles and suffix == 'str':
                event.has_str_tag = True
        return event