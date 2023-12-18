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

import struct 
import logging

def read_int(fo, lenght=1):
    fmt = '{}i'.format(lenght)
    size = struct.calcsize(fmt)

    unpacked = struct.Struct(fmt).unpack(fo.read(size))
    if lenght==1: return unpacked[0]
    return unpacked

def read_float(fo, lenght=1):
    fmt = '{}f'.format(lenght)
    size = struct.calcsize(fmt)

    unpacked = struct.Struct(fmt).unpack(fo.read(size))
    if lenght==1: return unpacked[0]
    return unpacked

def read_float3(fo):
    fmt = '3f'
    size = struct.calcsize(fmt)

    return tuple(struct.Struct(fmt).unpack(fo.read(size)))

def read_long(fo, lenght=1):
    fmt = '{}i'.format(lenght)
    size = struct.calcsize(fmt)

    unpacked = struct.Struct(fmt).unpack(fo.read(size))
    if lenght==1: return unpacked[0]
    return unpacked

def read_short(fo, lenght=1):
    fmt = '{}H'.format(lenght)
    size = struct.calcsize(fmt)

    unpacked = struct.Struct(fmt).unpack(fo.read(size))
    if lenght==1: return unpacked[0]
    return unpacked

def read_string(fo):
    lenght = read_long(fo)
    fmt = '{}s'.format(lenght)
    size = struct.calcsize(fmt)

    unpacked = struct.Struct(fmt).unpack(fo.read(size))
    return unpacked[0]

def read_byte(fo, lenght=1):
    fmt = '{}b'.format(lenght)
    size = struct.calcsize(fmt)

    unpacked = struct.Struct(fmt).unpack(fo.read(size))
    if lenght==1: return unpacked[0]
    return unpacked
    
def read_matrix4(fo):
    fmt = '4f'
    size = struct.calcsize(fmt)

    unpacked = [
        struct.Struct(fmt).unpack(fo.read(size)),
        struct.Struct(fmt).unpack(fo.read(size)),
        struct.Struct(fmt).unpack(fo.read(size)),
        struct.Struct(fmt).unpack(fo.read(size))
    ]
    return unpacked
    

def write_long(fo, value):
    fmt = 'i'
    fo.write(struct.Struct(fmt).pack(value))

def write_short(fo, value):
    fmt = 'H'
    fo.write(struct.Struct(fmt).pack(value))

def write_float3(fo, v1, v2, v3):
    fmt = '3f'
    fo.write(struct.Struct(fmt).pack(v1, v2, v3))

def write_byte(fo, value):
    fmt = 'b'
    fo.write(struct.Struct(fmt).pack(value))

def write_float(fo, value):
    fmt = 'f'
    try:
        fo.write(struct.Struct(fmt).pack(value))
    except struct.error as e:
        logging.error('failed to write %s value as float' % value)
        raise e

def write_matrix4(fo, value):
    fmt = '4f'

    for row in range(4):
        fo.write(struct.Struct(fmt).pack(*value[row]))

def write_string(fo, value):
    lenght = len(value)
    fmt = '{}s'.format(lenght)
    write_long(fo, lenght)
    fo.write(struct.Struct(fmt).pack(value))