import os
from typing import List
from .bf2_common import Vec3

class BF2OccluderPlanesException(Exception):
    pass

class Group:
    def __init__(self):
        self.planes = list()
        self.verts = list()

class BF2OccluderPlanes:
    def __init__(self, occ_file='', name=''):
        if name:
            self.name = name
        elif occ_file:
            self.name = os.path.splitext(os.path.basename(occ_file))[0]
        else:
            raise BF2OccluderPlanesException("occ_file or name required")
        
        self.groups : List[Group] = list()

        if not occ_file:
            return

        with open(occ_file, "r") as f:
            line = f.readline()
            if not line or not line.startswith('OCCLUDERPLANESv0.2'):
                raise BF2OccluderPlanesException("missing or unsupported .occ file version")

            while True:
                line = f.readline()
                if not line:
                    break
                if not line.startswith('GROUP'):
                    raise BF2OccluderPlanesException("invalid .occ file format")
                group = Group()
                self.groups.append(group)
                plane_count = int(f.readline())
                for _ in range(plane_count):
                    indices = tuple([int(l) for l in f.readline().split()])
                    if len(indices) != 4:
                        raise BF2OccluderPlanesException("invalid .occ file format")
                    group.planes.append(indices)
                vert_count = int(f.readline())
                for _ in range(vert_count):
                    vertices = tuple([float(l) for l in f.readline().split()])
                    if len(vertices) != 3:
                        raise BF2OccluderPlanesException("invalid .occ file format")
                    group.verts.append(Vec3(*vertices))

    def export(self, export_path):
        with open(export_path, "w") as f:
            f.write('OCCLUDERPLANESv0.2\n')
            for group in self.groups:
                f.write('GROUP\n')
                f.write(f'{len(group.planes)}\n')
                for plane in group.planes:
                    f.write(" ".join(map(str, plane)) + '\n')
                f.write(f'{len(group.verts)}\n')
                for vert in group.verts:
                    f.write(' '.join(map(str, vert)) + '\n')
