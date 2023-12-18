# The MIT License (MIT)

# Copyright (c) 2019 Nikita Gotsko

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

import os
import logging

class BF2Mesh(object):
    def __init__(self, filename=None,
            isSkinnedMesh=False, isBundledMesh=False, isStaticMesh=False, isCollisionMesh=False):
        if filename:
            self.filename = filename
            logging.debug('BF2Mesh::filename %s', filename)
            file_extension = os.path.splitext(filename)[1].lower()

            self.isSkinnedMesh = (file_extension == '.skinnedmesh')
            self.isBundledMesh = (file_extension == '.bundledmesh')
            self.isStaticMesh = (file_extension == '.staticmesh')
            self.isCollisionMesh = (file_extension == '.collisionmesh')
        else:
            self.isSkinnedMesh = isSkinnedMesh
            self.isBundledMesh = isBundledMesh
            self.isStaticMesh = isStaticMesh
            self.isCollisionMesh = isCollisionMesh
        self.isLoaded = False