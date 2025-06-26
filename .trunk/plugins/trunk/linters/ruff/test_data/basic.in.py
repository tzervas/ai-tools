def main():
    try:
        pass
    except (Exception, TypeError):
        pass

# trunk-ignore(ruff/F401)
import json
import sys


class NoDocstring(object):
    def __init__(self, arg1):
        self._attr1 = arg1

class Globe(object):
    def __init__(self):
        self.shape = 'spheroid'
