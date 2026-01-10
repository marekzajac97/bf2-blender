# BSP Builder
A python native extenstion module for fast binary space partitioning of BF2 collision meshes. The pure-python implementation of this module does exist as well but it's painfully slow, therefore it's only used as a backup.

## Prerequisites
- A compiler with C++14 support
- A Python installation (and development headers) that matches Blender's interpreter version.

## Building
```
python setup.py build_ext --build-lib ../io_scene_bf2/core/bf2/
```
