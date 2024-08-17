import os
import sys

DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.join(DIR, "pybind11"))

from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools import setup

__version__ = "0.0.1"

ext_modules = [
    Pybind11Extension(
        "bsp_builder",
        ["src/main.cpp"]
    ),
]

setup(
    name="bsp_builder",
    version=__version__,
    author="Marek Zajac",
    author_email="marekzajac97@gmail.com",
    url="https://github.com/marekzajac97/bf2-blender",
    description="Import and export asset files for DICE's Refractor 2 engine",
    long_description="",
    ext_modules=ext_modules,
    cmdclass={"build_ext": build_ext},
    zip_safe=False,
    python_requires=">=3.11",
)
