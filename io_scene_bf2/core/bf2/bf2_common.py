import math
from .fileutils import FileUtils

def load_n_elems(f : FileUtils, struct_type, count, **kwargs):
    return [struct_type.load(f, **kwargs) for _ in range(count)]

def _calc_bounds(verts, func):
    axes = [[ v[i] for v in verts] for i in range(3)]
    return Vec3(*[func(axis) for axis in axes])

def calc_bounds(verts):
    _min = _calc_bounds(verts, min)
    _max = _calc_bounds(verts, max)
    return (_min, _max)

class Quat:
    def __init__(self, x=0.0, y=0.0, z=0.0, w=1.0):
        self.x = x
        self.y = y
        self.z = z
        self.w = w
    
    def __getitem__(self, axis):
        if axis == 0:
            return self.x
        elif axis == 1:
            return self.y
        elif axis == 2:
            return self.z
        elif axis == 3:
            return self.w
        else:
            raise IndexError()
    
    def __setitem__(self, axis, val):
        if axis == 0:
            self.x = val
        elif axis == 1:
            self.y = val
        elif axis == 2:
            self.z = val
        elif axis == 3:
            self.w = val
        else:
            raise IndexError()

    def set(self, axis, angle):
        s = math.sin(angle / 2)
        self.x = axis.x * s
        self.y = axis.y * s
        self.z = axis.z * s
        self.w = math.cos(angle / 2)
        return self
    
    def invert(self):
        self.x = -self.x
        self.y = -self.y
        self.z = -self.z
        return self
    
    def multiply(self, a):
        self.multiply_quats(self, a)
        return self

    def multiply_quats(self, a, b):
        qax, qay, qaz, qaw = a
        qbx, qby, qbz, qbw = b
        self.x = qax * qbw + qaw * qbx + qay * qbz - qaz * qby
        self.y = qay * qbw + qaw * qby + qaz * qbx - qax * qbz
        self.z = qaz * qbw + qaw * qbz + qax * qby - qay * qbx
        self.w = qaw * qbw - qax * qbx - qay * qby - qaz * qbz
        return self

    def copy(self):
        return Quat(self.x, self.y, self.z, self.w)

    @classmethod
    def load(cls, f : FileUtils):
        obj = cls()
        obj.x = f.read_float()
        obj.y = f.read_float()
        obj.z = f.read_float()
        obj.w = f.read_float()
        return obj

    def save(self, f : FileUtils):
        f.write_float(self.x)
        f.write_float(self.y)
        f.write_float(self.z)
        f.write_float(self.w)
    
    def __repr__(self):
        return f"{self.x:.3f}/{self.y:.3f}/{self.z:.3f}/{self.w:.3f}"

    def __eq__(self, other):
        if isinstance(other, Vec3):
            return (self.x == other.x and
                    self.y == other.y and
                    self.z == other.z and
                    self.w == self.w)
        return False

class Vec3:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = x
        self.y = y
        self.z = z
    
    def __getitem__(self, axis):
        if axis == 0:
            return self.x
        elif axis == 1:
            return self.y
        elif axis == 2:
            return self.z
        else:
            raise IndexError()
    
    def __setitem__(self, axis, val):
        if axis == 0:
            self.x = val
        elif axis == 1:
            self.y = val
        elif axis == 2:
            self.z = val
        else:
            raise IndexError()
    
    def add(self, a):
        self.x += a.x
        self.y += a.y
        self.z += a.z
        return self

    def sub(self, a):
        self.x -= a.x
        self.y -= a.y
        self.z -= a.z
        return self

    def scale(self, a):
        self.x *= a
        self.y *= a
        self.z *= a
        return self

    def apply_quat(self, q):
        x, y, z = self
        qx, qy, qz, qw = q

        ix = qw * x + qy * z - qz * y
        iy = qw * y + qz * x - qx * z
        iz = qw * z + qx * y - qy * x
        iw = -qx * x - qy * y - qz * z

        self.x = ix * qw + iw * -qx + iy * -qz - iz * -qy
        self.y = iy * qw + iw * -qy + iz * -qx - ix * -qz
        self.z = iz * qw + iw * -qz + ix * -qy - iy * -qx
        return self

    def length(self):
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    @staticmethod
    def distance_squared(v1, v2):
        dx = v1.x - v2.x
        dy = v1.y - v2.y
        dz = v1.z - v2.z
        return dx * dx + dy * dy + dz * dz

    @staticmethod
    def distance(v1, v2):
        return math.sqrt(Vec3.distance_squared(v1, v2))

    @staticmethod
    def lerp(v1, v2, alpha):
        x = v1.x + (v2.x - v1.x) * alpha
        y = v1.y + (v2.y - v1.y) * alpha
        z = v1.z + (v2.z - v1.z) * alpha
        return Vec3(x, y, z)

    def normalize(self):
        if self.length() == 0.0:
            return self
        return self.scale(1.0 / self.length())

    def rotate(self, m):
        v_cpy = self.copy()
        self.x = v_cpy.x * m[0][0] + v_cpy.y * m[1][0] + v_cpy.z * m[2][0]
        self.y = v_cpy.x * m[0][1] + v_cpy.y * m[1][1] + v_cpy.z * m[2][1]
        self.z = v_cpy.x * m[0][2] + v_cpy.y * m[1][2] + v_cpy.z * m[2][2]
        return self

    def dot_product(self, a):
        return self.x * a.x + self.y * a.y + self.z * a.z
    
    def cross_product(self, a):
        result = Vec3()
        result.x = self.y * a.z - self.z * a.y
        result.y = self.z * a.x - self.x * a.z
        result.z = self.x * a.y - self.y * a.x
        return result

    def copy(self):
        return Vec3(self.x, self.y, self.z)

    @classmethod
    def load(cls, f : FileUtils):
        obj = cls()
        obj.x = f.read_float()
        obj.y = f.read_float()
        obj.z = f.read_float()
        return obj

    def save(self, f : FileUtils):
        f.write_float(self.x)
        f.write_float(self.y)
        f.write_float(self.z)
    
    def __repr__(self):
        return f"{self.x:.3f}/{self.y:.3f}/{self.z:.3f}"
    
    def __eq__(self, other):
        if isinstance(other, Vec3):
            return (self.x == other.x and
                    self.y == other.y and
                    self.z == other.z)
        return False

class Mat4:
    def __init__(self, m=None):
        if m is not None:
            self.m = list()
            for row in m:
                row = list(row)
                if len(row) != 4:
                    raise ValueError(f"Bad matrix {m}")
                self.m.append(row)
            if len(self.m) != 4:
                    raise ValueError(f"Bad matrix {m}") 
        else:
            self.m =[[1, 0, 0, 0],
                     [0, 1, 0, 0],
                     [0, 0, 1, 0],
                     [0, 0, 0, 1]]

    @classmethod
    def load(cls, f : FileUtils):
        obj = cls()
        obj.m[0] = list(f.read_float(count=4))
        obj.m[1] = list(f.read_float(count=4))
        obj.m[2] = list(f.read_float(count=4))
        obj.m[3] = list(f.read_float(count=4))
        return obj

    def save(self, f : FileUtils):
        f.write_float(self.m[0])
        f.write_float(self.m[1])
        f.write_float(self.m[2])
        f.write_float(self.m[3])

    @staticmethod
    def rotation(angle, axis):
        c = math.cos(angle)
        s = math.sin(angle)
        if axis == 'X':
            m = [[1, 0,  0, 0],
                 [0, c, -s, 0],
                 [0, s,  c, 0],
                 [0, 0,  0, 1]]
        elif axis == 'Y':
            m = [[c, 0, s, 0],
                 [0, 1, 0, 0],
                 [-s, 0, c, 0],
                 [0, 0, 0, 1]]
        elif axis == 'Z':
            m = [[c, -s, 0, 0],
                 [s,  c, 0, 0],
                 [0,  0, 1, 0],
                 [0,  0, 0, 1]]
        else:
            raise ValueError(f"Bad axis {axis}")
        return Mat4(m)

    def __getitem__(self, row):
        return self.m[row]
    
    def __setitem__(self, row, val):
        self.m[row] = val

    def __repr__(self):
        return repr(self.m)