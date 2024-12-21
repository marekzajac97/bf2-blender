from ..bf2_common import Vec3
from ..fileutils import FileUtils
from .bf2_visiblemesh import BF2VisibleMesh, Lod
import math

class BF2SamplesException(Exception):
    pass

def is_pow_two(n):
    return (n & (n-1) == 0) and n != 0

def clamp(v, min_val, max_val):
    return max(min(v, max_val), min_val)

def triangle_area(face):
    v1, v2, v3 = face
    d1 = v1.copy().sub(v2).length()
    d2 = v2.copy().sub(v3).length()
    d3 = v3.copy().sub(v1).length()
    h = (d1 + d2 + d3) * 0.5
    v = h * (h - d1) * (h - d2) * (h - d3)
    if v < 0:
        return 0
    return math.sqrt(v)

def texel_to_point(v1, v2, v3, t1, t2, t3, p):
    d = ((t2[0] - t1[0]) * (t3[1] - t1[1]) - (t2[1] - t1[1]) * (t3[0] - t1[0]))

    if abs(d) < EPSILON:
        return Vec3()

    i = 1 / d
    s = i * ((t3[1] - t1[1]) * (p[0] - t1[0]) - (t3[0] - t1[0]) * (p[1] - t1[1]))
    t = i * (-(t2[1] - t1[1]) * (p[0] - t1[0]) + (t2[0] - t1[0]) * (p[1] - t1[1]))

    ret = Vec3()
    ret.x = v1[0] + s * (v2[0] - v1[0]) + t * (v3[0] - v1[0])
    ret.y = v1[1] + s * (v2[1] - v1[1]) + t * (v3[1] - v1[1])
    ret.z = v1[2] + s * (v2[2] - v1[2]) + t * (v3[2] - v1[2])

    return ret

def dot_product_2d(v1, v2):
    return v1[0] * v2[0] + v1[1] * v2[1]

def distance_2d(a, b):
    return math.sqrt(((a[0] - b[0]) * (a[0] - b[0])) + ((a[1] - b[1]) * (a[1] - b[1])))

def point_dist_to_segment(p, v1, v2):
    v = [0, 0]
    w = [0, 0]

    v[0] = v2[0] - v1[0]
    v[1] = v2[1] - v1[1]
    w[0] = p[0] - v1[0]
    w[1] = p[1] - v1[1]

    c1 = dot_product_2d(w, v)
    if c1 <= 0:
        return distance_2d(p, v1)
    c2 = dot_product_2d(v, v)
    if c2 <= c1:
        return distance_2d(p, v2)
    
    if abs(c2) < EPSILON:
        b = 0
    else:
        b = c1 / c2

    pb = [0, 0]
    pb[0] = v1[0] + b * v[0]
    pb[1] = v1[1] + b * v[1]
    
    return distance_2d(p, pb)

def triangle_test(v1, v2, v3, p):
    if (p[0] - v1[0]) * (v2[1] - v1[1]) - (p[1] - v1[1]) * (v2[0] - v1[0]) > 0: return False
    if (p[0] - v2[0]) * (v3[1] - v2[1]) - (p[1] - v2[1]) * (v3[0] - v2[0]) > 0: return False
    if (p[0] - v3[0]) * (v1[1] - v3[1]) - (p[1] - v3[1]) * (v1[0] - v3[0]) > 0: return False
    return True

def inside_triangle(t1, t2, t3, p, margin):
    if triangle_test(t1, t2, t3, p):
        return 1
    
    if margin > 0:
        if point_dist_to_segment(p, t1, t2) < margin:
            return 2
        if point_dist_to_segment(p, t2, t3) < margin:
            return 2
        if point_dist_to_segment(p, t3, t1) < margin:
            return 2
    return 0

def closes_point_on_line(a, b, p):
    ap = [0, 0]
    ab = [0, 0]
    
    ap[0] = p[0] - a[0]
    ap[1] = p[1] - a[1]
    
    ab[0] = b[0] - a[0]
    ab[1] = b[1] - a[1]

    ab2 = ab[0] * ab[0] + ab[1] * ab[1]
    ap_ab = ap[0] * ab[0] + ap[1] * ab[1]
    
    if abs(ab2) < EPSILON:
        t = ap_ab
    else:
        t = ap_ab / ab2

    if t < 0: t = 0
    if t > 1: t = 1
    
    return [a[0] + ab[0] * t, a[1] + ab[1] * t]

def closest_point_on_triangle(t1, t2, t3, p):
    if triangle_test(t1, t2, t3, p):
        return p
    cp = [0, 0]
    tcp = [0, 0]

    cp = closes_point_on_line(t1, t2, p)
    d = distance_2d(cp, p)
    
    tcp = closes_point_on_line(t2, t3, p)
    td = distance_2d(tcp, p)
    if td < d:
        cp = tcp
        d = td

    tcp = closes_point_on_line(t3, t1, p)
    td = distance_2d(tcp, p)
    if td < d:
        cp = tcp
        d = td

    return cp

def gen_normal(p1, p2, p3):
    v1 = p3.copy().sub(p1)
    v2 = p2.copy().sub(p1)
    n = v1.cross_product(v2)
    n.normalize()
    return n

def fix_normal(n, rep):
    if any([i == float("NaN") for i in n]):
        n.x, n.y, n.z = rep.x, rep.y, rep.z

EPSILON = 0.0000001


class Sample:
    def __init__(self):
        self.pos = Vec3()
        self.dir = Vec3()
        self.face = -1


class BF2Samples:
    def __init__(self, bf2_lod : Lod, size,
                 sample_padding=6,
                 use_edge_margin=True, uv_chan=4):
        x, y = size
        if not is_pow_two(x) or not is_pow_two(y):
            raise BF2SamplesException("Lightmap dimensions must be power of two!")

        self.bf2_lod = bf2_lod
        self.mapsizex = x
        self.mapsizey = y
        self.use_edge_margin = use_edge_margin
        self.sample_padding = sample_padding
        self.uv_chan = uv_chan

    def export(self, filename):
        samples = self._gen_samples()
        self._gen_sample_padding(samples)

        with open(filename, "wb") as f:
            samples_file = FileUtils(f)
            samples_file.write_raw(b'SMP2')
            # samples
            samples_file.write_dword(self.mapsizex)
            samples_file.write_dword(self.mapsizey)
            for sample in samples:
                sample.pos.save(samples_file)
                sample.dir.save(samples_file)
                samples_file.write_dword(sample.face, signed=True)

            # faces
            face_num = sum([len(bf2_mat.faces) for bf2_mat in self.bf2_lod.materials])
            samples_file.write_dword(face_num)
            for bf2_mat in self.bf2_lod.materials:
                for face in bf2_mat.faces:
                    verts = [bf2_mat.vertices[v] for v in face]
                    for vert in verts:
                        [samples_file.write_float(v) for v in vert.position]
                        [samples_file.write_float(v) for v in vert.normal]

    def pixel_idx(self, x, y):
        return x + (self.mapsizex * y)

    def _gen_samples(self):
        samplenum = self.mapsizex * self.mapsizey

        samples = list()
        
        # compute texel scale
        sx = 1 / self.mapsizex
        sy = 1 / self.mapsizey
        
        # compute texel center offset
        ox = sx / 2
        oy = sy / 2

        # edge margin
        if self.use_edge_margin:
            edgemargin = max(sx, sy)
        else:
            edgemargin = 0

        # sample flag
        # if 0:  sample is not rasterized
        # if 1:  sample is inside triangle interior, sample cannot be overwritten
        # if 2:  sample is inside triangle edge margin, may be replaced (by interior triangle sample only)
        sampleflag = list()

        for _ in range(samplenum):
            samples.append(Sample())
            sampleflag.append(0)

        bad_face_count = 0
        face_index = 0
        for bf2_mat in self.bf2_lod.materials:
            for face in bf2_mat.faces:
                bad_face = False
                vi1, vi2, vi3 = face

                # check if deleted (degenerate face)
                if vi1 == vi2 or vi1 == vi3 or vi2 == vi3:
                    bad_face = True

                v1, v2, v3 = [Vec3(*bf2_mat.vertices[v].position) for v in face]
                t1, t2, t3 = [getattr(bf2_mat.vertices[v], f'texcoord{self.uv_chan}') for v in face]

                # skip face if extremely small area
                if triangle_area((v1, v2, v3)) < EPSILON:
                    bad_face = True

                ignore_tri_errors = False

                # skip triangle if it is very thin
                if not ignore_tri_errors:
                    DEGENERATEFACEANGLE = math.radians(0.001)
                    a1 = v1.copy().sub(v2).angle_to(v1.copy().sub(v3))
                    a2 = v2.copy().sub(v1).angle_to(v2.copy().sub(v3))
                    a3 = v3.copy().sub(v2).angle_to(v3.copy().sub(v1))
                    if any([a < DEGENERATEFACEANGLE for a in (a1, a2, a3)]):
                        bad_face = True

                if not bad_face:
                    # compute triangle rect bounds
                    fminx = min(min(t1[0], t2[0]), t3[0]) * (self.mapsizex - 1)
                    fminy = min(min(t1[1], t2[1]), t3[1]) * (self.mapsizey - 1)
                    fmaxx = max(max(t1[0], t2[0]), t3[0]) * (self.mapsizex - 1)
                    fmaxy = max(max(t1[1], t2[1]), t3[1]) * (self.mapsizey - 1)

                    minx = int(round(fminx, 3))
                    miny = int(round(fminy, 3))
                    maxx = int(round(fmaxx, 3))
                    maxy = int(round(fmaxy, 3))

                    # take in account triangle edge margin
                    if self.use_edge_margin:
                        minx = minx - 1
                        miny = miny - 1
                        maxx = maxx + 1
                        maxy = maxy + 1

                    # clamp bounds to map size
                    minx = clamp(minx, 0, self.mapsizex - 1)
                    miny = clamp(miny, 0, self.mapsizey - 1)
                    maxx = clamp(maxx, 0, self.mapsizex - 1)
                    maxy = clamp(maxy, 0, self.mapsizey - 1)

                    # check if bounds are greater than 0
                    if maxx - minx == 0: bad_face = True
                    if maxy - miny == 0: bad_face = True

                if bad_face:
                    bad_face_count += 1
                else:
                    for x in range(minx, maxx + 1):
                        for y in range(miny, maxy + 1):
                            # compute pixel index
                            i = self.pixel_idx(x, y)

                            # only samples that are not rasterized yet or edge margin samples
                            if sampleflag[i] != 1:
                                # compute UV position (texel center)
                                p = [(x * sx) + ox, (y * sy) + oy]
                                tritest = inside_triangle(t1, t2, t3, p, edgemargin)

                                if tritest == 0:
                                    # triangle test failed, don't rasterize anything
                                    rasterize = False
                                elif tritest == 1:
                                    # interior sample, always rasterize these (can overwrite edge margin samples)
                                    rasterize = True
                                elif tritest == 2:
                                    if sampleflag[i] == 0:
                                        rasterize = True # no sample yet, rasterize edge margin
                                        # modify point so it isn't outside triangle
                                        p = closest_point_on_triangle(t1, t2, t3, p)
                                    else:
                                        rasterize = False # already have edge margin sample, keep it

                                if rasterize:
                                    n1, n2, n3 = [Vec3(*bf2_mat.vertices[v].normal) for v in face]

                                    # fix normal if singularity
                                    facenorm = gen_normal(v1, v2, v3)
                                    fix_normal(n1, facenorm)
                                    fix_normal(n2, facenorm)
                                    fix_normal(n3, facenorm)
                                    
                                    # set samples
                                    samples[i].pos = texel_to_point(v1, v2, v3, t1, t2, t3, p)
                                    samples[i].dir = texel_to_point(n1, n2, n3, t1, t2, t3, p).normalize()
                                    samples[i].face = face_index
                                    sampleflag[i] = tritest
                face_index += 1
        return samples

    def _gen_sample_padding(self, samples):
        for _ in range(self.sample_padding):
            tmp = [-1] * len(samples)

            for x in range(self.mapsizex):
                for y in range(self.mapsizey):
                    cs = self.pixel_idx(x, y)
                    if samples[cs].face == -1: 
                        j = -1
                        if j < 0: 
                            if y - 1 > 0: 
                                s = self.pixel_idx(x, y - 1)
                                if samples[s].face > -1:  j = s

                        if j < 0: 
                            if y + 1 < self.mapsizey - 1: 
                                s = self.pixel_idx(x, y + 1)
                                if samples[s].face > -1:  j = s

                        if j < 0: 
                            if x - 1 > 0: 
                                s = self.pixel_idx(x - 1, y)
                                if samples[s].face > -1:  j = s

                        if j < 0: 
                            if x + 1 < self.mapsizex - 1: 
                                s = self.pixel_idx(x + 1, y)
                                if samples[s].face > -1:  j = s

                        if j > -1: 
                            tmp[cs] = j

            for j in range(len(samples)):
                if tmp[j] > -1:
                    samples[j] = samples[tmp[j]]
