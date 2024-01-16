import enum
from .main_console import MainConsole
import types


def _str_to_vec(str_form, length):
    v = tuple(map(lambda x: float(x), str_form.split('/')))
    if len(v) != length:
        raise ValueError("bad vector length")
    return v

def _vec_to_str(vec):
    return '/'.join(f'{num:.4f}' for num in vec)

class InstanceMethod(object):

    def __init__(self, func):
        self.func = func

    def __get__(self, obj, objtype=None):
        active = BF2Engine().get_manager(objtype or type(obj)).active_template
        if active:
            return types.MethodType(self.func, active)

        def not_active_dummy(*args, **kwargs):
            return 'Template not active'
        return not_active_dummy

def instancemethod(func):
    return InstanceMethod(func)

class Template:
    MANAGED_TYPE = None

    def __init__(self, name):
        self.name = name

    def __str__(self):
        return '<{} {}>'.format(self.__class__.__name__, self.name)
    
    def __repr__(self):
        return '"%s"' % str(self)

    @classmethod
    def create(cls, *args):
        BF2Engine().get_manager(cls).create(*args)

    @classmethod
    def active(cls, *args):
        BF2Engine().get_manager(cls).active(*args)


class TemplateManager():
    MANAGED_TYPE = Template

    def __init__(self):
        self.templates = dict()
        self.active_template = None

    def create(self, *args):
        new_template = self.MANAGED_TYPE(*args)
        name = new_template.name.lower()
        if name in self.templates:
            template = self.templates[name]
            self.active_template = template
            return None
        self.templates[name] = new_template
        self.active_template = new_template
        return new_template

    def active(self, template):
        template_low = template.lower()
        temp = self.templates.get(template_low)
        if temp:
            self.active_template = temp
        else:
            self.active_template = None
            return 'Activating non exisiting {}'.format(self.type.__name__)

class GeometryTemplate(Template):

    TYPES = {
        'staticmesh': 'StaticMesh',
        'bundledmesh': 'BundledMesh',
        'skinnedmesh': 'SkinnedMesh'
    }

    def __init__(self, geometry_type, name):
        super(GeometryTemplate, self).__init__(name)
        if geometry_type.lower() in self.TYPES:
            self.geometry_type = self.TYPES[geometry_type.lower()]
        else:
            raise ValueError(f"Unknown geometry type {geometry_type}")

        self.nr_of_animated_uv_matrix = 0

    def make_script(self, f):
        f.write(f'GeometryTemplate.create {self.geometry_type} {self.name}\n')
        if self.nr_of_animated_uv_matrix:
            f.write(f'GeometryTemplate.nrOfAnimatedUVMatrix {self.nr_of_animated_uv_matrix}\n')


class CollisionMeshTemplate(Template):
    def __init__(self, name):
        super(CollisionMeshTemplate, self).__init__(name)

    def make_script(self, f):
        f.write(f'CollisionManager.createTemplate {self.name}\n')


class ObjectTemplate(Template):

    class _ObjectTemplateType(enum.IntEnum):
        pass

    class _PhysicsType(enum.IntEnum):
        NONE = 0
        POINT = 1
        PLATFORM = 2
        MESH = 3
        ROTATIONAL_POINT = 4

    class ChildObject:
        def __init__(self, name):
            self.template_name = name
            self.template = None
            self.position = (0, 0, 0)
            self.rotation = (0, 0, 0)

    def __init__(self, object_type, name):
        super(ObjectTemplate, self).__init__(name)
        self.type = object_type
        self._active_child = None
        self.parent = None
        self.children = []
        self.collmesh = None
        self.geom = None
        self.geom_part = 0
        self.col_part = 0
        self.has_collision_physics = False
        self.col_material_map = dict()
        self.has_mobile_physics = False
        self.creator_name = ''
        self.physics_type = ObjectTemplate._PhysicsType.NONE
        self.save_in_separate_file = False

    def make_script(self, f):
        f.write(f'ObjectTemplate.create {self.type} {self.name}\n')

        if self.save_in_separate_file:
            f.write(f'ObjectTemplate.saveInSeparateFile {int(self.save_in_separate_file)}\n')
        if self.creator_name:
            f.write(f'ObjectTemplate.creator {self.creator_name}\n')

        if self.collmesh:
            f.write(f'ObjectTemplate.collisionMesh {self.collmesh.name}\n')
            for mat_index, mat in sorted(self.col_material_map.items()):
                f.write(f'ObjectTemplate.mapMaterial {mat_index} {mat} 0\n')

        if self.col_part:
            f.write(f'ObjectTemplate.collisionPart {self.col_part}\n')
        if self.has_collision_physics:
            f.write(f'ObjectTemplate.hasCollisionPhysics {int(self.has_collision_physics)}\n')
        if self.physics_type:
            f.write(f'ObjectTemplate.physicsType {self.physics_type}\n')
        if self.has_mobile_physics:
            f.write(f'ObjectTemplate.hasMobilePhysics {int(self.has_mobile_physics)}\n')
        if self.geom:
            f.write(f'ObjectTemplate.geometry {self.geom.name}\n')
        if self.geom_part:
            f.write(f'ObjectTemplate.geometryPart {self.geom_part}\n')

        for child in self.children:
            f.write(f'ObjectTemplate.addTemplate {child.template_name}\n')
            if child.position != (0, 0, 0):
                f.write(f'ObjectTemplate.setPosition {_vec_to_str(child.position)}\n')
            if child.rotation != (0, 0, 0):
                f.write(f'ObjectTemplate.setRotation {_vec_to_str(child.rotation)}\n')
        f.write('\n')

        for child in self.children:
            child.template.make_script(f)

    @classmethod
    def activeSafe(cls, *args):
        BF2Engine().get_manager(cls).active(*args)

    @instancemethod
    def addTemplate(self, template):
        self._active_child = self.ChildObject(template)
        self.children.append(self._active_child)

    @instancemethod
    def geometry(self, template):
        self.geom = template

    @instancemethod
    def collisionMesh(self, template):
        self.collmesh = template

    @instancemethod
    def geometryPart(self, val):
        self.geom_part = int(val)

    @instancemethod
    def collisionPart(self, val):
        self.col_part = int(val)
    
    @instancemethod
    def hasCollisionPhysics(self, val):
        self.has_collision_physics = bool(val)

    @instancemethod
    def setPosition(self, vec):
        if self._active_child is None:
            return
        self._active_child.position = _str_to_vec(vec, 3)

    @instancemethod
    def setRotation(self, vec):
        if self._active_child is None:
            return
        self._active_child.rotation = _str_to_vec(vec, 3)
    
    @instancemethod
    def mapMaterial(self, mat_idx, mat_name, unk):
        self.col_material_map[int(mat_idx)] = mat_name
    
    @instancemethod
    def physicsType(self, val):
        self.physics_type = ObjectTemplate._PhysicsType(int(val))

    @instancemethod
    def creator(self, val):
        self.creator_name = val

    @instancemethod
    def saveInSeparateFile(self, val):
        self.save_in_separate_file = bool(val)


class ObjectTemplateManager(TemplateManager):
    MANAGED_TYPE = ObjectTemplate

    def activeSafe(self, object_type, template):
        temp = self.active(template)
        if not temp or temp.type.lower() != object_type.lower():
            self.active_template = None

    def add_bundle_childs(self, object_template):
        for child in object_template.children:
            child.template = self.templates[child.template_name.lower()]
            child.template.parent = object_template
            self.add_bundle_childs(child.template)


class GeometryTemplateManager(TemplateManager):
    MANAGED_TYPE = GeometryTemplate


class CollisionManager(TemplateManager):
    MANAGED_TYPE = CollisionMeshTemplate

    @classmethod
    def createTemplate(cls, name):
        self = BF2Engine().get_manager(cls.MANAGED_TYPE)
        self.create(name)


class BF2Engine():
    _instance = None

    def get_manager(self, _type) -> TemplateManager:
        for manager in self.managers:
            if _type == manager.MANAGED_TYPE:
                return manager

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls._instance, cls):
            cls._instance = object.__new__(cls, *args, **kwargs)
            cls._instance.init()
        return cls._instance

    def init(self):
        self.managers = list()
        self.managers.append(ObjectTemplateManager())
        self.managers.append(GeometryTemplateManager())
        self.managers.append(CollisionManager())
        self.main_console : MainConsole = MainConsole(silent=True)
        self.main_console.register_object(ObjectTemplate)
        self.main_console.register_object(GeometryTemplate)
        self.main_console.register_object(CollisionManager)

    @classmethod
    def shutdown(cls):
        cls._instance = None
