# The MIT License (MIT)

# Copyright (c) 2023 Marek Zajac

# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

bl_info = {
    "name" : "BF2 Tools",
    "author" : "Marek Zajac",
    "description" : "Import and export asset files for DICE's Refractor 2 engine",
    "blender" : (4, 1, 1),
    "version" : (0, 7, 7),
    "location": "File -> Import/Export -> BF2",
    "warning" : "",
    "doc_url": "https://github.com/marekzajac97/bf2-blender/blob/main/docs/README.md",
    "tracker_url": "https://github.com/marekzajac97/bf2-blender/issues/new",
    "category" : "Import-Export"
}

PLUGIN_NAME = __package__

from .operators import ops_main

def register():
    ops_main.register()

def unregister():
    ops_main.unregister()

if __name__ == "__main__":
    register()