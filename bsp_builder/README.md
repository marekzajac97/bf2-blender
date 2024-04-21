# BSP Builder
The pure-python implementation of the CollisionMesh export exists but it's painfully slow, therefore this C++ exstenstion module is required for a fast CollisionMesh export.

## Prerequisites
- A compiler with C++14 support
- CMake >= 3.4 (or 3.14+ on Windows)
- A Python install with version matching Blender's interpreter

## Building
```
mkdir build && cd build
cmake ..
make
```