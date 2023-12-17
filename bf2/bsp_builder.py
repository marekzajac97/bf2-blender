from typing import List, Optional
from .bf2_common import Vec3

class PolyType:
    FRONT = 0,
    BACK = 1,
    COPLANAR = 2,
    STRADDLE = 3,

class Poly:
    def __init__(self, points, face_ref):
        self.face_ref = face_ref
        self.points : List[Vec3] = points

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
        return self._split_poly(plane) != 0

    def _split_poly(self, plane):
        sides = 0
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
                            sides |= 1 << vertex

                last_side_parallel = denom == 0.0

        return sides

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
    def __init__(self):
        self.front_polys : List[Poly] = None
        self.back_polys : List[Poly] = None
        self.front_node : Optional[Node] = None
        self.back_node : Optional[Node] = None
        self.split_plane : Plane = None


class BspBuilder:

    def __init__(self, verts, faces):
        self.verts = verts
        self.faces = faces

        polys = list()
        for face in faces:
            points = list()
            points.append(verts[face.verts[0]].copy())
            points.append(verts[face.verts[1]].copy())
            points.append(verts[face.verts[2]].copy())
            polys.append(Poly(points, face))
        self.root = self._build_bsp_tree(polys)

    def _get_all_verts(self, polys : List[Poly]):
        verts = set()
        for poly in polys:
            verts.add(poly.face_ref.verts[0])
            verts.add(poly.face_ref.verts[1])
            verts.add(poly.face_ref.verts[2])
        return [self.verts[v] for v in verts]

    def _get_all_planes(self, polys : List[Poly]):
        planes = list()
        for vert in self._get_all_verts(polys):
            planes.append(Plane(vert.x, 0))
            planes.append(Plane(vert.y, 1))
            planes.append(Plane(vert.z, 2))
        return planes

    def _find_best_split_plane(self, polys : List[Poly]):
        COPLANAR_WEIGHT = 0.5 # puts more emphasis on keeping to minimum coplanar polygons
        INTERSECT_WIEGHT = 1 # puts more emphasis on keeping to minimum intersecting polygons
        SPLIT_WEIGHT = 1 # puts more emphasis on equal split on front/back polygons
        MIN_SPLIT_METRIC = 0.5 # minimum acceptable metric, when to stop splitting

        best_metric = float("inf")
        best_split_plane = None

        for split_plane in self._get_all_planes(polys):
            
            coplanar : List[Poly] = list()
            intersect : List[Poly] = list()
            front : List[Poly] = list()
            back : List[Poly] = list()

            for poly in polys:
                c = poly.classify(split_plane)
                if c == PolyType.STRADDLE:
                    intersect.append(poly)
                elif c == PolyType.COPLANAR:
                    coplanar.append(poly)
                elif c == PolyType.FRONT:
                    front.append(poly)
                elif c == PolyType.BACK:
                    back.append(poly)
                else:
                    raise RuntimeError()

            if not front or not back: # can't split into two sets
                continue

            split_ratio = len(front) / (len(front) + len(back))
            intersect_ratio = len(intersect) / len(polys)
            coplanar_ratio = len(coplanar) / len(polys)

            metric = (abs(0.5 - split_ratio) * SPLIT_WEIGHT +
                      intersect_ratio * INTERSECT_WIEGHT +
                      coplanar_ratio * COPLANAR_WEIGHT)

            if metric > MIN_SPLIT_METRIC:
                continue

            if metric < best_metric:
                best_metric = metric
                best_split_plane = split_plane

        return best_split_plane

    def _build_bsp_tree(self, polys : List[Poly], level=0):

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

        root = Node()
        root.split_plane = split_plane
        root.front_node = self._build_bsp_tree(front, level+1)
        if root.front_node is None:
             root.front_polys = front

        root.back_node = self._build_bsp_tree(back, level+1)
        if root.back_node is None:
             root.back_polys = back

        return root
