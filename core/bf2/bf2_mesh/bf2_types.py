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

import enum

USED = 0
UNUSED = 255

# copypasta from DX SDK 'Include/d3d9types.h' enum _D3DDECLTYPE to address
# vert attribute vartype variable
class D3DDECLTYPE(enum.IntEnum):
    FLOAT1 = 0  # 1D float expanded to (value, 0., 0., 1.)
    FLOAT2 = 1  # 2D float expanded to (value, value, 0., 1.)
    FLOAT3 = 2  # 3D float expanded to (value, value, value, 1.)
    FLOAT4 = 3  # 4D float
    D3DCOLOR = 4  # 4D packed unsigned bytes mapped to 0. to 1. range
    UBYTE4 = 5,
    SHORT2 = 6,
    SHORT4 = 7,
    UBYTE4N = 8,
    SHORT2N = 9,
    SHORT4N = 10,
    USHORT2N = 11,
    USHORT4N = 12,
    UDEC3 = 13,
    DEC3N = 14,
    FLOAT16_2 = 15,
    FLOAT16_4 = 16,
    UNUSED = 17,  # When the type field in a decl is unused.

    def get_struct_fmt(self):
        _TYPE_TO_FORMAT = {
            D3DDECLTYPE.FLOAT1: '1f',
            D3DDECLTYPE.FLOAT2: '2f',
            D3DDECLTYPE.FLOAT3: '3f',
            D3DDECLTYPE.FLOAT4: '4f',
            D3DDECLTYPE.D3DCOLOR: '4B',
        }

        return _TYPE_TO_FORMAT[self]


# copypasta from DX SDK 'Include/d3d9types.h' enum _D3DDECLUSAGE to
# address vert attribute usage variable
class D3DDECLUSAGE(enum.IntEnum):
    POSITION = 0
    BLENDWEIGHT = 1
    BLENDINDICES = 2
    NORMAL = 3
    PSIZE = 4
    TEXCOORD0 = 5
    TANGENT = 6
    BINORMAL = 7
    TESSFACTOR = 8
    POSITIONT = 9
    COLOR = 10
    FOG = 11
    DEPTH = 12
    SAMPLE = 13
    # bf2 enums for additional UVs much larger than dx to avoid collisions?
    TEXCOORD1 = 1 << 8 | 5
    TEXCOORD2 = 2 << 8 | 5
    TEXCOORD3 = 3 << 8 | 5
    TEXCOORD4 = 4 << 8 | 5

class D3DPRIMITIVETYPE(enum.IntEnum):
    POINTLIST = 1
    LINELIST = 2
    LINESTRIP = 3
    TRIANGLELIST = 4
    TRIANGLESTRIP = 5
    TRIANGLEFAN = 6
