# BSP Builder
A python native extenstion module for fast binary space partitioning of BF2 collision meshes. The pure-python implementation of this module does exist as well but it's painfully slow, therefore it's only used as a backup.

## Prerequisites
- A compiler with C++14 support
- A python installation with version matching target Blender's interpreter. Alternatively, just the target Blender build can be used by setting your `PATH` variable to point to its python executable.

    - on Windows
    ```
    set PATH="<BLENDER_INSTAL_DIR>\<BLENDER_VERSION>\python\bin;%PATH%"
    ```

    - on Unix (Linux/macOS)
    ```
    export PATH="<BLENDER_INSTAL_DIR>/<BLENDER_VERSION>/python/bin:$PATH"
    ```

## Building
```
python setup.py build_ext --build-lib ../io_scene_bf2/core/bf2/
```
