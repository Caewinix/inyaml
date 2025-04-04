import yaml
import yaml.composer


class Composer(yaml.composer.Composer):
    def compose_node(self, parent, index):
        event = self.peek_event()
        node = super().compose_node(parent, index)
        if isinstance(event, yaml.ScalarEvent) and getattr(event, 'has_str_tag', False):
            node.has_str_tag = True
        return node