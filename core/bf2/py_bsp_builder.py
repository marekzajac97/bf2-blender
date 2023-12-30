from typing import List, Tuple, Optional
from .bf2_common import Vec3

class PolyType:
    FRONT = 0,
    BACK = 1,
    COPLANAR = 2,
    STRADDLE = 3

class Poly:
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

    def _intersects(self, plane):
        last_side_parallel = False

        if self.normal != plane.normal:
            for vertex in range(len(self.points)):
                prev_vert = vertex - 1 if vertex != 0 else len(self.points) - 1

                edge_delta = self.points[vertex].copy().sub( self.points[prev_vert])
                denom = edge_delta.dot_product(plane.normal)
                if denom:
                    numer = self.points[prev_vert].dot_product(plane.normal) + plane.d
                    t = -numer / denom
                    if not (last_side_parallel and t == 0.0):
                        if t > 0.0 and t < 0.999999:
                            return True

                last_side_parallel = denom == 0.0
        return False

    def classify(self, plane):
        if self._intersects(plane):
            return PolyType.STRADDLE
        else:
            delta = self.center.copy().sub(plane.point)
            dotp = delta.dot_product(plane.normal)
            if dotp == 0.0:
                return PolyType.COPLANAR
            elif dotp < 0:
                return PolyType.FRONT
            else:
                return PolyType.BACK

class Plane:
    def __init__(self, val, axis):
        self.val = val
        self.axis = axis

        self.normal = Vec3()
        self.normal[axis] = 1
        self.point = Vec3()
        self.point[axis] = val
        self.d = -self.normal.dot_product(self.point)


class Node:
    def __init__(self, split_plane):
        self.front_faces : List[Poly] = None
        self.back_faces : List[Poly] = None
        self.front_node : Optional[Node] = None
        self.back_node : Optional[Node] = None
        self.split_plane : Plane = split_plane

class BspBuilder:

    def __init__(self, verts : Tuple[float], faces : Tuple[int]):
        self.verts = [Vec3(*v) for v in verts]
        self.faces = faces

        polys = list()
        for face_idx, face in enumerate(faces):
            polys.append(Poly(face, self.verts, face_idx))
        self.root = self._build_bsp_tree(polys)

    def _get_all_planes(self, polys : List[Poly]):
        planes_to_check = set() # set of (vert, axis)
        for poly in polys:
            for i, vert in enumerate(poly.indexes):
                planes_to_check.add((vert, i))

        for plane in planes_to_check:
            vert, i = plane
            yield Plane(self.verts[vert][i], i)

    def _find_best_split_plane(self, polys : List[Poly]):
        COPLANAR_WEIGHT = 0.5 # puts more emphasis on keeping to minimum coplanar polygons
        INTERSECT_WIEGHT = 1 # puts more emphasis on keeping to minimum intersecting polygons
        SPLIT_WEIGHT = 1 # puts more emphasis on equal split on front/back polygons
        MIN_SPLIT_METRIC = 0.5 # minimum acceptable metric, when to stop splitting

        best_metric = float("inf")
        best_split_plane = None

        for split_plane in self._get_all_planes(polys):
            coplanar_count = 0
            intersect_count = 0
            front_count = 0
            back_count = 0

            for poly in polys:
                c = poly.classify(split_plane)
                if c == PolyType.STRADDLE:
                    intersect_count += 1
                elif c == PolyType.COPLANAR:
                    coplanar_count += 1
                elif c == PolyType.FRONT:
                    front_count += 1
                elif c == PolyType.BACK:
                    back_count += 1
                else:
                    raise RuntimeError()

            if front_count == 0 or back_count == 0: # can't split into two sets
                continue

            split_ratio = front_count / (front_count + back_count)
            intersect_ratio = intersect_count / len(polys)
            coplanar_ratio = coplanar_count / len(polys)

            metric = (abs(0.5 - split_ratio) * SPLIT_WEIGHT +
                      intersect_ratio * INTERSECT_WIEGHT +
                      coplanar_ratio * COPLANAR_WEIGHT)

            if metric > MIN_SPLIT_METRIC:
                continue

            if metric < best_metric:
                best_metric = metric
                best_split_plane = split_plane

        return best_split_plane

    def _build_bsp_tree(self, polys : List[Poly]):

        split_plane = self._find_best_split_plane(polys)
        if split_plane is None:
            return None # no suitable split plane, stop splitting

        front : List[Poly] = list()
        back : List[Poly] = list()

        for poly in polys:
            c = poly.classify(split_plane)
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
