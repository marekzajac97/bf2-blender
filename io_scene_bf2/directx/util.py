# MIT License

# Copyright (c) 2022-2025 matyalatte

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Utils for I/O."""

import ctypes
from ctypes.util import find_library
import os
import platform


def mkdir(directory):
    """Make directory."""
    os.makedirs(directory, exist_ok=True)


def get_ext(file):
    """Get file extension."""
    return file.split('.')[-1].lower()


def get_size(f):
    pos = f.tell()
    f.seek(0, 2)
    size = f.tell()
    f.seek(pos)
    return size

def get_os_name():
    return platform.system()


def is_windows():
    return get_os_name() == 'Windows'


def is_linux():
    return get_os_name() == 'Linux'


def is_mac():
    return get_os_name() == 'Darwin'


def is_arm():
    return 'arm' in platform.machine().lower()


def get_dll_close_from_lib(lib_name):
    """Return dll function to unlaod DLL if the library has it."""
    dlpath = find_library(lib_name)
    if dlpath is None:
        # DLL not found.
        return None
    try:
        lib = ctypes.CDLL(dlpath)
        if hasattr(lib, "dlclose"):
            return lib.dlclose
    except OSError:
        pass
    # dlclose not found.
    return None


def get_dll_close():
    """Get dll function to unload DLL."""
    if is_windows():
        return ctypes.windll.kernel32.FreeLibrary
    else:
        # Search libc, libdl, and libSystem
        for lib_name in {"c", "dl", "System"}:
            dlclose = get_dll_close_from_lib(lib_name)
            if dlclose is not None:
                return dlclose
    # Failed to find dlclose
    return None

OS_TO_EXT = {
    'Windows': '.dll',
    'Linux': '.so',
    'Darwin': '.dylib',
}

def find_local_library(dir, lib_name):
    for f in os.listdir(dir):
        name, ext = os.path.splitext(f)
        if ext != OS_TO_EXT.get(get_os_name()):
            continue
        if name.startswith(lib_name) or name.startswith("lib" + lib_name):
            return os.path.join(dir, f)
    return None
