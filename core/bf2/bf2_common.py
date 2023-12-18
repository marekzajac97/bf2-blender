import math
from .fileutils import FileUtils

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
        qax = a.x
        qay = a.y
        qaz = a.z
        qaw = a.w
        qbx = b.x
        qby = b.y
        qbz = b.z
        qbw = b.w
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
        x = self.x
        y = self.y
        z = self.z
        qx = q.x
        qy = q.y
        qz = q.z
        qw = q.w

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

    def normalize(self):
        if self.length() == 0.0:
            return self
        return self.scale(1.0 / self.length())

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
