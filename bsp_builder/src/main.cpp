#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <vector>
#include <tuple>

typedef std::tuple<int, int, int> Face;
typedef std::tuple<float, float, float> Vertex;

struct Vec3 {
    float x, y, z;

    Vec3(float x, float y, float z) : x(x), y(y), z(z) {};
    Vec3() : x(0.0f), y(0.0f), z(0.0f) {};
    Vec3(Vertex v) : x(std::get<0>(v)),
                     y(std::get<1>(v)),
                     z(std::get<2>(v)) {};

    float length() const {
        return ::std::sqrt(x * x + y * y + z * z);
    }

    Vec3& scale(float s) {
        x = x * s;
        y = y * s;
        z = z * s;
        return *this;
    }

    Vec3& normalize() {
        float len = length();
        if (len == 0.0f) return *this;
        return scale(1.0f / len);
    }

    Vec3& add(const Vec3& v) {
        x += v.x;
        y += v.y;
        z += v.z;
        return *this;
    }

    Vec3& sub(const Vec3& v) {
        x -= v.x;
        y -= v.y;
        z -= v.z;
        return *this;
    }

    Vec3& sub_vectors(const Vec3& v1, const Vec3& v2) {
        x = v1.x - v2.x;
        y = v1.y - v2.y;
        z = v1.z - v2.z;
        return *this;
    }

    Vec3 cross_product(const Vec3& v) const {
        Vec3 result;
        result.x = y * v.z - z * v.y;
        result.y = z * v.x - x * v.z;
        result.z = x * v.y - y * v.x;
        return result;
    }

    float dot_product(const Vec3& v) const {
        return v.x * x + v.y * y + v.z * z;
    }

    bool equals(const Vec3& v) const {
        return x == v.x && y == v.y && z == v.z;
    }
};

class Poly;

class Plane {
public:
    Plane(float val, int axis) : val(val), axis(axis) {
        switch (axis) {
        case 0:
            normal.x = 1.0f;
            point.x = val;
            break;
        case 1:
            normal.y = 1.0f;
            point.y = val;
            break;
        case 2:
            normal.z = 1.0f;
            point.z = val;
            break;
        default:
            assert(0);
        }

        d = -normal.dot_product(point);
    };

    const float val;
    const int axis;
private:

    Vec3 normal;
    Vec3 point;
    float d;

    friend class Poly;
};

enum class PolyType {
    FRONT,
    BACK,
    COPLANAR,
    STRADDLE
};

class Poly {
public:
    Poly(const Face& face, const std::vector<Vertex>& verts)
    {
        points[0] = verts[std::get<0>(face)];
        points[1] = verts[std::get<1>(face)];
        points[2] = verts[std::get<2>(face)];

        indexes[0] = std::get<0>(face);
        indexes[1] = std::get<1>(face);
        indexes[2] = std::get<2>(face);

        for (Vec3& point : points) {
            center.add(point);
        }
        center.scale(1.0f / points.size());

        Vec3 a, b;
        a.sub_vectors(points[0], points[1]);
        b.sub_vectors(points[2], points[1]);
        normal = a.cross_product(b);
        normal.normalize();
        d = -normal.dot_product(center);
    }

    PolyType clasify(Plane& plane) const {
        if (intersects(plane)) {
            return PolyType::STRADDLE;
        }
        else {
            Vec3 delta;
            delta.sub_vectors(center, plane.point);
            float dotp = delta.dot_product(plane.normal);
            if (dotp == 0.0f)
                return PolyType::COPLANAR;
            else if (dotp < 0.0f)
                return PolyType::FRONT;
            else
                return PolyType::BACK;
        }
    }

    std::array<int, 3> indexes;
private:
    bool intersects(Plane& plane) const {
        bool last_side_parallel = false;
        if (!normal.equals(plane.normal)) {
            Vec3 EdgeDelta;
            float numer, denom, t;

            for (unsigned short vertex = 0; vertex < points.size(); vertex++) {
                unsigned short prevVertex = vertex ? vertex - 1 : points.size() - 1;

                EdgeDelta.sub_vectors(points[vertex], points[prevVertex]);
                denom = EdgeDelta.dot_product(plane.normal);

                if (denom) {
                    numer = points[prevVertex].dot_product(plane.normal) + plane.d;
                    t = -numer / denom;

                    if (!(last_side_parallel && t == 0.0f)) {
                        if (t > 0.0f && t < 0.999999f) {
                            return true;
                        }
                    }
                }
                last_side_parallel = (denom == 0.0f);
            }
        }
        return false;
    }

private:
    std::array<Vec3, 3> points;
    Vec3 center;
    Vec3 normal;
    float d;
};

struct Node {

    Node(const Plane& split_plane) : split_plane(split_plane) {}

    std::vector<size_t> front_faces;
    std::vector<size_t> back_faces;
    Node* front_node = nullptr;
    Node* back_node = nullptr;
    const Plane split_plane;
};

typedef std::array<Plane, 3> AxisPlanes;

class BspBuilder {
public:
    BspBuilder(const std::vector<Vertex>& verts, const std::vector<Face>& faces,
               float coplanar_weight = 0.5f, float intersect_weight = 1.0f,
               float split_weight = 1.0f, float min_split_metric = 0.5f)
        :
        vert_count(verts.size()),
        coplanar_weight(coplanar_weight),
        intersect_weight(intersect_weight),
        split_weight(split_weight),
        min_split_metric(min_split_metric)
    {
        polys.reserve(faces.size());
        std::vector<size_t> poly_indexes;
        poly_indexes.reserve(faces.size());
        for (int i = 0; i < faces.size(); ++i) {
            const Face& face = faces[i];
            poly_indexes.push_back(i);
            polys.push_back(Poly(face, verts));
        }

        planes.reserve(vert_count * 3);
        for (int i = 0; i < vert_count; ++i) {
            Vec3 vertx = verts[i];
            AxisPlanes planes_per_axis = {
                Plane(vertx.x, 0),
                Plane(vertx.y, 1),
                Plane(vertx.z, 2)
            };
            planes.push_back(planes_per_axis);
        }

        root = build_bsp_tree(poly_indexes);
    }
    Node* root = nullptr;

    ~BspBuilder() {
        if (root == nullptr) {
            return;
        }
        destroy_bsp_tree(root);
    }

private:
    std::vector<Poly> polys; // lookup for face_idx -> poly
    std::vector<AxisPlanes> planes; // lookup for vert_index -> 3 planes created by this vert
    size_t vert_count;
    const float coplanar_weight; // puts more emphasis on keeping to minimum coplanar polygons
    const float intersect_weight; // puts more emphasis on keeping to minimum intersecting polygons
    const float split_weight; // puts more emphasis on equal split on front / back polygons
    const float min_split_metric; // minimum acceptable metric, when to stop splitting

    Node* build_bsp_tree(std::vector<size_t>& poly_indexes) {

        Plane* split_plane = find_best_split_plane(poly_indexes);
        if (split_plane == nullptr) {
            return nullptr;
        }

        std::vector<size_t> front;
        std::vector<size_t> back;

        for (size_t poly_index : poly_indexes) {
            const Poly& poly = polys[poly_index];
            switch (poly.clasify(*split_plane)) {
            case PolyType::STRADDLE:
            case PolyType::COPLANAR:
                front.push_back(poly_index);
                back.push_back(poly_index);
                break;
            case PolyType::FRONT:
                front.push_back(poly_index);
                break;
            case PolyType::BACK:
                back.push_back(poly_index);
                break;
            default:
                assert(0);
            }
        }

        Node* node = new Node(*split_plane);
        node->front_node = build_bsp_tree(front);
        if (node->front_node == nullptr)
            node->front_faces = std::move(front);

        node->back_node = build_bsp_tree(back);
        if (node->back_node == nullptr)
            node->back_faces = std::move(back);

        return node;
    }

    Plane* find_best_split_plane(std::vector<size_t>& poly_indexes) {
        float best_metric = std::numeric_limits<float>::infinity();
        Plane* best_split_plane = nullptr;

        std::unique_ptr<bool[]> p_plane_flags = std::make_unique<bool[]>(vert_count * 3);
        bool* plane_flags = p_plane_flags.get();
        std::memset(plane_flags, 0, vert_count * 3 * sizeof(bool));

        size_t poly_count = poly_indexes.size();

        for (size_t test_poly_index : poly_indexes) {
            const Poly& test_poly = polys[test_poly_index];
            for (int i = 0; i < 3; ++i) {
                // create a plane from each poly vert and axis
                int vert = test_poly.indexes[i];

                if (plane_flags[3 * vert + i]) {
                    continue; // plane already checked
                }

                plane_flags[3 * vert + i] = true;
                Plane& split_plane = planes[vert][i];

                size_t coplanar_count = 0;
                size_t intersect_count = 0;
                size_t front_count = 0;
                size_t back_count = 0;

                for (size_t poly_index : poly_indexes) {
                    const Poly& poly = polys[poly_index];
                    switch (poly.clasify(split_plane)) {
                        case PolyType::STRADDLE:
                            intersect_count++;
                            break;
                        case PolyType::COPLANAR:
                            coplanar_count++;
                            break;
                        case PolyType::FRONT:
                            front_count++;
                            break;
                        case PolyType::BACK:
                            back_count++;
                            break;
                        default:
                            assert(0);
                    }
                }

                if (front_count == 0 || back_count == 0) // can't split into two sets
                    continue;

                float split_ratio = (float)front_count / (float)(front_count + back_count);
                float intersect_ratio = (float)intersect_count / (float)poly_count;
                float coplanar_ratio = (float)coplanar_count / (float)poly_count;

                float metric = std::abs(0.5f - split_ratio) * split_weight +
                               intersect_ratio * intersect_weight +
                               coplanar_ratio * coplanar_weight;

                if (metric > min_split_metric)
                    continue;

                if (metric < best_metric) {
                    best_metric = metric;
                    best_split_plane = &split_plane;
                }
            }
        }

        return best_split_plane;
    }

    void destroy_bsp_tree(Node* node) {
        if (node->front_node) {
            destroy_bsp_tree(node->front_node);
        }
        if (node->back_node) {
            destroy_bsp_tree(node->back_node);
        }
        delete node;
    }
};

namespace py = pybind11;

PYBIND11_MODULE(bsp_builder, m) {

    py::class_<BspBuilder>(m, "BspBuilder")
        .def(py::init<const std::vector<Vertex>&, const std::vector<Face>&, float, float, float, float>(),
            py::arg("verts"), py::arg("faces"),
            py::arg("coplanar_weight") = 0.5f,
            py::arg("intersect_weight") = 1.0f,
            py::arg("split_weight") = 1.0f,
            py::arg("min_split_metric") = 0.5f)
        .def_readonly("root", &BspBuilder::root);

    py::class_<Plane>(m, "Plane")
        .def(py::init<float, int>())
        .def_readonly("val", &Plane::val)
        .def_readonly("axis", &Plane::axis);

    py::class_<Node>(m, "Node")
        .def(py::init<const Plane&>())
        .def_readonly("split_plane", &Node::split_plane)
        .def_readonly("front_faces", &Node::front_faces)
        .def_readonly("back_faces", &Node::back_faces)
        .def_readonly("front_node", &Node::front_node)
        .def_readonly("back_node", &Node::back_node);
}
