from typing import List, Tuple, Optional
from .bf2_common import Vec3

PRE_CACHE_SPLIT_PLANES = True

class PolyType:
    FRONT = 0,
    BACK = 1,
    COPLANAR = 2,
    STRADDLE = 3

class Poly:
    __slots__ = ('face_idx', 'indexes', 'points',
                 'center', 'normal', 'd')

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

                edge_delta = self.points[vertex].copy().sub(self.points[prev_vert])
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
    __slots__ = ('val', 'axis', 'normal',
                 'point', 'd', 'face_cache')

    def __init__(self, val, axis):
        self.val = val
        self.axis = axis

        self.normal = Vec3()
        self.normal[axis] = 1
        self.point = Vec3()
        self.point[axis] = val
        self.d = -self.normal.dot_product(self.point)
        self.face_cache = None

    def cache_faces(self, polys):
        self.face_cache = list()
        for poly in polys:
            c = poly.classify(self)
            self.face_cache.append(c)

    def classify(self, poly):
        if self.face_cache is not None:
            return self.face_cache[poly.face_idx]
        return poly.classify(self)


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
                 'min_split_metric', 'split_planes', 'root')

    def __init__(self, verts : Tuple[float], faces : Tuple[int],
                 complanar_weigth = 0.5, intersect_weight = 1.0,
                 split_weight = 1.0, min_split_metric = 0.5):
        self.verts = [Vec3(*v) for v in verts]
        self.faces = faces

        self.complanar_weigth = complanar_weigth # puts more emphasis on keeping to minimum coplanar polygons
        self.intersect_weight = intersect_weight # puts more emphasis on keeping to minimum intersecting polygons
        self.split_weight = split_weight # puts more emphasis on equal split on front/back polygons
        self.min_split_metric = min_split_metric # minimum acceptable metric, when to stop splitting

        polys = list()
        for face_idx, face in enumerate(faces):
            polys.append(Poly(face, self.verts, face_idx))

        self.split_planes = dict()
        for vert, i in self._get_all_split_plane_ids(polys):
            split_plane = Plane(self.verts[vert][i], i)
            if PRE_CACHE_SPLIT_PLANES:
                split_plane.cache_faces(polys)
            self.split_planes[(vert, i)] = split_plane

        self.root = self._build_bsp_tree(polys)

    def _get_all_split_plane_ids(self, polys : List[Poly]):
        planes_to_check = set() # set of (vert, axis)
        for poly in polys:
            for i, vert in enumerate(poly.indexes):
                planes_to_check.add((vert, i))

        for plane in planes_to_check:
            yield plane

    def _find_best_split_plane(self, polys : List[Poly]) -> Plane:
        best_metric = float("inf")
        best_split_plane = None

        for split_plane_id in self._get_all_split_plane_ids(polys):
            split_plane = self.split_planes[split_plane_id]

            coplanar_count = 0
            intersect_count = 0
            front_count = 0
            back_count = 0

            for poly in polys:
                c = split_plane.classify(poly)
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

            metric = (abs(0.5 - split_ratio) * self.split_weight +
                      intersect_ratio * self.intersect_weight +
                      coplanar_ratio * self.complanar_weigth)

            if metric > self.min_split_metric:
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
