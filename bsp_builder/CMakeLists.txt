cmake_minimum_required(VERSION 3.4...3.18)
project(bsp_builder)

set(PYBIND11_PYTHON_VERSION "3.10")

add_subdirectory(pybind11)
pybind11_add_module(bsp_builder src/main.cpp)
