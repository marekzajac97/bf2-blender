from typing import List, Tuple, Optional
from bisect import bisect_left, bisect_right
from .bf2_common import Vec3

class PolyType:
    FRONT = 0,
    BACK = 1,
    COPLANAR = 2,
    STRADDLE = 3

class Poly:
    __slots__ = ('face_idx', 'indexes', 'points',
                 'center', 'normal', 'd',
                 'min_coord', 'max_coord')

    def __init__(self, face, verts, face_idx):
        self.face_idx = face_idx
        self.indexes = face
        self.points : Tuple[Vec3] = (
            verts[face[0]].copy(),
            verts[face[1]].copy(),
            verts[face[2]].copy()
        )

        self.center = Vec3()
        for point in self.points:
            self.center.add(point)
        self.center.scale(1.0 / len(self.points))

        a = self.points[0].copy().sub(self.points[1])
        b = self.points[2].copy().sub(self.points[1])
        self.normal = a.cross_product(b)
        self.normal.normalize()

        self.d = -self.normal.dot_product(self.center)

        self.min_coord = Vec3(
            min(self.points[0].x, self.points[1].x, self.points[2].x),
            min(self.points[0].y, self.points[1].y, self.points[2].y),
            min(self.points[0].z, self.points[1].z, self.points[2].z),
        )
        self.max_coord = Vec3(
            max(self.points[0].x, self.points[1].x, self.points[2].x),
            max(self.points[0].y, self.points[1].y, self.points[2].y),
            max(self.points[0].z, self.points[1].z, self.points[2].z),
        )


class Plane:
    __slots__ = ('val', 'axis', 'normal', 'point', 'd')

    def __init__(self, val, axis):
        self.val = val
        self.axis = axis

        self.normal = Vec3()
        self.normal[axis] = 1
        self.point = Vec3()
        self.point[axis] = val
        self.d = -self.normal.dot_product(self.point)

    def classify(self, poly):
        d = self.axis
        s = self.val
        l = poly.min_coord[d]
        r = poly.max_coord[d]
        if l < s < r:
            return PolyType.STRADDLE
        if l == r == s:
            return PolyType.COPLANAR
        if poly.center[d] < s:
            return PolyType.FRONT
        if poly.center[d] > s:
            return PolyType.BACK
        return PolyType.COPLANAR


class Node:
    __slots__ = ('front_faces', 'back_faces', 'front_node',
                 'back_node', 'split_plane')

    def __init__(self, split_plane):
        self.front_faces : List[Poly] = None
        self.back_faces : List[Poly] = None
        self.front_node : Optional[Node] = None
        self.back_node : Optional[Node] = None
        self.split_plane : Plane = split_plane

class BspBuilder:
    __slots__ = ('verts', 'faces', 'complanar_weigth',
                 'intersect_weight', 'split_weight',
                 'min_split_metric', 'root')

    def __init__(self, verts : Tuple[float], faces : Tuple[int],
                 complanar_weigth = 0.5, intersect_weight = 1.0,
                 split_weight = 1.0, min_split_metric = 0.5):
        self.verts = [Vec3(*v) for v in verts]
        self.faces = faces

        self.complanar_weigth = complanar_weigth
        self.intersect_weight = intersect_weight
        self.split_weight = split_weight
        self.min_split_metric = min_split_metric

        polys = list()
        for face_idx, face in enumerate(faces):
            polys.append(Poly(face, self.verts, face_idx))

        self.root = self._build_bsp_tree(polys)

    def _find_best_split_plane(self, polys : List[Poly]) -> Plane:
        best_metric = float("inf")
        best_split_plane = None
        total_polys = len(polys)

        for axis in range(3):
            positions = sorted(set(
                point[axis] for poly in polys for point in poly.points
            ))
            M = len(positions)
            if M == 0:
                continue

            back_diff = [0] * (M + 1)
            intersect_diff = [0] * (M + 1)
            front_diff = [0] * (M + 1)
            coplanar_at = [0] * M

            for poly in polys:
                l = poly.min_coord[axis]
                r = poly.max_coord[axis]

                if l == r:
                    idx = bisect_left(positions, l)
                    if idx < M and positions[idx] == l:
                        back_diff[0] += 1
                        back_diff[idx] -= 1
                        coplanar_at[idx] += 1
                        front_diff[idx + 1] += 1
                    else:
                        back_diff[0] += 1
                        back_diff[idx] -= 1
                        front_diff[idx] += 1
                else:
                    back_end = bisect_right(positions, l)
                    front_start = bisect_left(positions, r)

                    if back_end > 0:
                        back_diff[0] += 1
                        back_diff[back_end] -= 1

                    if back_end < front_start:
                        intersect_diff[back_end] += 1
                        intersect_diff[front_start] -= 1

                    if front_start < M:
                        front_diff[front_start] += 1

            back = intersect = front = 0
            for i in range(M):
                back += back_diff[i]
                intersect += intersect_diff[i]
                front += front_diff[i]
                coplanar = coplanar_at[i]

                if front == 0 or back == 0:
                    continue

                split_ratio = front / (front + back)
                intersect_ratio = intersect / total_polys
                coplanar_ratio = coplanar / total_polys

                metric = (abs(0.5 - split_ratio) * self.split_weight +
                          intersect_ratio * self.intersect_weight +
                          coplanar_ratio * self.complanar_weigth)

                if metric > self.min_split_metric:
                    continue

                if metric < best_metric:
                    best_metric = metric
                    best_split_plane = Plane(positions[i], axis)

        return best_split_plane

    def _build_bsp_tree(self, polys : List[Poly]):

        split_plane = self._find_best_split_plane(polys)
        if split_plane is None:
            return None

        front : List[Poly] = list()
        back : List[Poly] = list()

        for poly in polys:
            c = split_plane.classify(poly)
            if c == PolyType.STRADDLE or c == PolyType.COPLANAR:
                front.append(poly)
                back.append(poly)
            elif c == PolyType.FRONT:
                front.append(poly)
            elif c == PolyType.BACK:
                back.append(poly)
            else:
                raise RuntimeError()

        node = Node(split_plane)
        node.front_node = self._build_bsp_tree(front)
        if node.front_node is None:
             node.front_faces = [f.face_idx for f in front]

        node.back_node = self._build_bsp_tree(back)
        if node.back_node is None:
             node.back_faces =  [f.face_idx for f in back]

        return node
