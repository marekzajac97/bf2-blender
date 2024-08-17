PLUGIN_NAME = __package__

from .operators import ops_main

def register():
    ops_main.register()

def unregister():
    ops_main.unregister()

if __name__ == "__main__":
    register()
