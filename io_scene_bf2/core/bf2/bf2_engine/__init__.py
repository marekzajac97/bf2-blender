import enum
import os

from .common import console_command
from .main_console import MainConsole
from .file_manager import FileManager, FileManagerFileNotFound

def _str_to_vec(str_form, length):
    v = tuple(map(lambda x: float(x), str_form.split('/')))
    if len(v) != length:
        raise ValueError("bad vector length")
    return v

def _vec_to_str(vec):
    return '/'.join(f'{num:.4f}' for num in vec)

class Manager:
    def __init__(self, engine=None):
        self.engine = engine
        self.active_obj = None

    def __getattr__(self, name):
        if name.startswith('__') or name == 'active_obj':
            raise AttributeError(name)
        obj = self.__dict__.get('active_obj')
        seen = set()
        while obj is not None and id(obj) not in seen:
            seen.add(id(obj))
            try:
                return getattr(obj, name)
            except AttributeError:
                obj = getattr(obj, 'active_obj', None)
        raise AttributeError(name)

    def __dir__(self):
        names = set(super().__dir__())
        obj = self.__dict__.get('active_obj')
        seen = set()
        while obj is not None and id(obj) not in seen:
            seen.add(id(obj))
            names.update(dir(obj))
            obj = getattr(obj, 'active_obj', None)
        return sorted(names)

class Template:
    MANAGED_TYPE = None

    def __init__(self, name):
        self.name = name

    def __str__(self):
        return '<{} {}>'.format(self.__class__.__name__, self.name)
    
    def __repr__(self):
        return '"%s"' % str(self)


class TemplateManager(Manager):
    MANAGED_TYPE = Template

    def __init__(self, engine=None):
        super(TemplateManager, self).__init__(engine)
        self.templates = dict()

    @console_command
    def create(self, *args):
        new_template = self.MANAGED_TYPE(*args, engine=self.engine)
        name = new_template.name.lower()
        if name in self.templates:
            template = self.templates[name]
            self.active_obj = template
            return None
        self.templates[name] = new_template
        self.active_obj = new_template
        return new_template

    @console_command
    def active(self, template):
        template_low = template.lower()
        temp = self.templates.get(template_low)
        if temp:
            self.active_obj = temp
        else:
            self.active_obj = None
            self.engine.main_console.report('Activating non exisiting template {}'.format(template))


BF2_OBJECT_TEMPLATE_TYPES  = [
    'AirDraftEffectBundle',
    'AmbientEffectArea',
    'AnimatedBundle',
    'AntennaObject',
    'AreaObject',
    'Bundle',
    'Camera',
    'ControlPoint',
    'Decal',
    'DestroyableObject',
    'DestroyableWindow',
    'DestroyableWindowsBundle',
    'DropVehicle',
    'DynamicBundle',
    'EffectBundle',
    'Emitter',
    'Engine',
    'EntryPoint',
    'EnvMap',
    'FloatingBundle',
    'ForceObject',
    'FreeCamera',
    'GenericFireArm',
    'GenericProjectile',
    'GrapplingHookRope',
    'GrapplingHookRopeContainer',
    'GroundEffectBundle',
    'HookLink',
    'Item',
    'ItemContainer',
    'Kit',
    'KitPart',
    'Ladder',
    'LadderContainer',
    'LandingGear',
    'LightSource',
    'MaskObject',
    'MeshParticleSystem',
    'NonScreenAlignedParticleSystem',
    'ObjectSpawner',
    'Obstacle',
    'OverheadCamera',
    'Parachute',
    'Particle',
    'ParticleSystemEmitter',
    'PlayerControlObject',
    'RemoteControlledObject',
    'RopeLink',
    'RotationalBundle',
    'Rotor',
    'SimpleObject',
    'Soldier',
    'Sound',
    'Spring',
    'SpriteParticle',
    'SpriteParticleSystem',
    'SupplyDepot',
    'SupplyObject',
    'TargetObject',
    'TrailSystem',
    'Trigger',
    'Triggerable',
    'TriggerableTarget',
    'TurnableRemoteControlledObject',
    'UAVVehicle',
    'WheelEffectBundle',
    'Wing',
    'Zipline',
    'ZiplineContainer',
    'ZiplineRope'
]

class ObjectTemplate(Template):

    class _ObjectTemplateType(enum.IntEnum):
        pass

    class _PhysicsType(enum.IntEnum):
        NONE = 0
        POINT = 1
        PLATFORM = 2
        MESH = 3
        ROTATIONALPOINT = 4

    class ChildObject:
        def __init__(self, name):
            self.template_name = name
            self.template = None
            self.position = (0, 0, 0)
            self.rotation = (0, 0, 0)

    def __init__(self, object_type, name, engine=None):
        super(ObjectTemplate, self).__init__(name)
        self.type = object_type
        self._active_child = None
        self.parent = None
        self.children = []
        self.collmesh = None
        self.geom = None
        self.geom_part = -1
        self.col_part = 0
        self.has_collision_physics = False
        self.col_material_map = dict()
        self.has_mobile_physics = False
        self.creator_name = ''
        self.physics_type = ObjectTemplate._PhysicsType.NONE
        self.save_in_separate_file = False
        self.anchor_point = None

        active_con = engine.main_console.get_active_con_file() if engine else None
        if active_con:
            self.location = active_con.lower()
        else:
            self.location = None

    def make_script(self, f):
        f.write(f'ObjectTemplate.create {self.type} {self.name}\n')

        if self.save_in_separate_file:
            f.write(f'ObjectTemplate.saveInSeparateFile {int(self.save_in_separate_file)}\n')

        if self.anchor_point:
            f.write(f'ObjectTemplate.anchor {_vec_to_str(self.anchor_point)}\n')

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
        if self.geom_part != -1:
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

    @console_command
    def addTemplate(self, template):
        self._active_child = self.ChildObject(template)
        self.children.append(self._active_child)

    @console_command
    def geometry(self, template):
        self.geom = template

    @console_command
    def collisionMesh(self, template):
        self.collmesh = template

    @console_command
    def geometryPart(self, val):
        self.geom_part = int(val)

    @console_command
    def collisionPart(self, val):
        self.col_part = int(val)
    
    @console_command
    def hasCollisionPhysics(self, val):
        self.has_collision_physics = bool(val)

    @console_command
    def setPosition(self, vec):
        if self._active_child is None:
            return
        self._active_child.position = _str_to_vec(vec, 3)

    @console_command
    def setRotation(self, vec):
        if self._active_child is None:
            return
        self._active_child.rotation = _str_to_vec(vec, 3)
    
    @console_command
    def mapMaterial(self, mat_idx, mat_name, unk):
        self.col_material_map[int(mat_idx)] = mat_name
    
    @console_command
    def physicsType(self, val):
        if val.isdigit():
            self.physics_type = ObjectTemplate._PhysicsType(int(val))
        else:
            self.physics_type = ObjectTemplate._PhysicsType[val.upper()]

    @console_command
    def creator(self, val):
        self.creator_name = val

    @console_command
    def saveInSeparateFile(self, val):
        self.save_in_separate_file = bool(val)

    @console_command
    def anchor(self, vec):
        self.anchor_point = _str_to_vec(vec, 3)

class ObjectTemplateManager(TemplateManager):
    MANAGED_TYPE = ObjectTemplate

    @console_command
    def activeSafe(self, object_type, template):
        temp = self.active(template)
        if temp and temp.type.lower() != object_type.lower():
            self.active_obj = None

    def add_bundle_childs(self, object_template, raise_on_missing=True):
        for child in object_template.children:
            try:
                child.template = self.templates[child.template_name.lower()]
            except KeyError:
                if raise_on_missing:
                    raise BF2EngineException(f"The definition of child ObjectTemplate '{child.template_name.lower()}' not found")
                self.engine.main_console.report(f"The definition of child ObjectTemplate '{child.template_name}' not found")
                continue
            child.template.parent = object_template
            self.add_bundle_childs(child.template, raise_on_missing)


class GeometryTemplate(Template):

    TYPES = {
        'staticmesh': 'StaticMesh',
        'bundledmesh': 'BundledMesh',
        'skinnedmesh': 'SkinnedMesh',
        'meshparticlemesh': 'MeshParticleMesh',
        'roadcompiled': 'RoadCompiled',
        'debugspheremesh': 'DebugSphereMesh'
    }

    _FILE_EXT = {
        'staticmesh': 'staticmesh',
        'bundledmesh': 'bundledmesh',
        'skinnedmesh': 'skinnedmesh',
        'meshparticlemesh': 'bundledmesh',
        'roadcompiled': 'mesh',
        'debugspheremesh': None
    }

    def __init__(self, geometry_type, name, engine=None):
        super(GeometryTemplate, self).__init__(name)
        if geometry_type.lower() in self.TYPES:
            self.geometry_type = self.TYPES[geometry_type.lower()]
        else:
            raise ValueError(f"Unknown geometry type {geometry_type}")

        self.nr_of_animated_uv_matrix = 0
        self.dont_generate_lightmaps = False

        active_con = engine.main_console.get_active_con_file() if engine else None
        if active_con:
            dir = os.path.dirname(active_con.lower())
            file_ext = self._FILE_EXT[geometry_type.lower()]
            if file_ext is None:
                self.location = None
            else:
                self.location = os.path.join(dir, 'Meshes', f'{name}.{file_ext}')
        else:
            self.location = None

    def make_script(self, f):
        f.write(f'GeometryTemplate.create {self.geometry_type} {self.name}\n')
        if self.nr_of_animated_uv_matrix:
            f.write(f'GeometryTemplate.nrOfAnimatedUVMatrix {self.nr_of_animated_uv_matrix}\n')

    @console_command
    def doNotGenerateLightmaps(self, b):
        self.dont_generate_lightmaps = bool(int(b))

class GeometryTemplateManager(TemplateManager):
    MANAGED_TYPE = GeometryTemplate


class CollisionMeshTemplate(Template):
    def __init__(self, name, engine=None):
        super(CollisionMeshTemplate, self).__init__(name)

        active_con = engine.main_console.get_active_con_file() if engine else None
        if active_con:
            dir = os.path.dirname(active_con.lower())
            self.location = os.path.join(dir, 'Meshes', f'{name}.collisionmesh')
        else:
            self.location = None

    def make_script(self, f):
        f.write(f'CollisionManager.createTemplate {self.name}\n')


class CollisionManager(TemplateManager):
    MANAGED_TYPE = CollisionMeshTemplate

    @console_command
    def createTemplate(self, name):
        self.create(name)


class Heightmap:
    def __init__(self, _type, offset_x, offset_z):
        self.type = _type # seems to be always Heightmap, might be Editable?
        self.cluster_offset = (offset_x, offset_z)
        # TODO find defaults
        self.size = (0, 0)
        self.scale = (1, 1, 1)
        self.bit_res = 8
        self.material_scale = 1.0
        self.raw_file = None
        self.mat_file = None

    @console_command
    def setSize(self, x, y):
        self.size = (int(x), int(y))

    @console_command
    def setScale(self, vec):
        self.scale = _str_to_vec(vec, 3)

    @console_command
    def setBitResolution(self, val):
        self.bit_res = int(val)

    @console_command
    def setMaterialScale(self, val):
        self.material_scale = float(val)

    @console_command
    def loadHeightData(self, val):
        self.raw_file = val

    @console_command
    def loadMaterialData(self, val):
        self.mat_file = val


class HeightmapCluster(Manager):
    MANAGED_TYPE = Heightmap

    def __init__(self, name, engine=None):
        super(HeightmapCluster, self).__init__(engine)
        self.name = name # maybe its type?
        # TODO find defaults
        self.cluster_size = None
        self.heightmap_size = None
        self.heightmaps = list()
        self.water_level = 0

    @console_command
    def setClusterSize(self, size):
        self.cluster_size = int(size)

    @console_command
    def setHeightmapSize(self, size):
        self.heightmap_size = int(size)

    @console_command
    def addHeightmap(self, _type, offset_x, offset_z):
        self.active_obj = Heightmap(_type, int(offset_x), int(offset_z))
        self.heightmaps.append(self.active_obj)

    @console_command
    def setSeaWaterLevel(self, val):
        self.water_level = float(val)

class HeightmapClusterManager(Manager):
    MANAGED_TYPE = HeightmapCluster

    def __init__(self, engine=None):
        super(HeightmapClusterManager, self).__init__(engine)
        self.clusters = list()
        self.active_obj = None

    @console_command
    def create(self, name):
        new_cluster = HeightmapCluster(name, self.engine)
        self.clusters.append(new_cluster)
        self.active_obj = new_cluster
        return new_cluster


class Object:
    def __init__(self, template):
        self.template = template
        self.is_overgrowth = False
        self.absolute_pos = (0, 0, 0)
        self.rot = (0, 0, 0)
        self.transform = None
        self.light_source_mask = 0
        self._layer = 0

    @console_command
    def isOvergrowth(self, flag):
        self.is_overgrowth = bool(int(flag))

    @console_command
    def absolutePosition(self, pos):
        self.absolute_pos = _str_to_vec(pos, 3)

    @console_command
    def absoluteTransformation(self, matrix_str):
        self.transform = list()
        for row in matrix_str.strip('[]').split(']['):
            self.transform.append(_str_to_vec(row, 4))

    @console_command
    def rotation(self, rot):
        self.rot = _str_to_vec(rot, 3)
    
    @console_command
    def layer(self, _layer):
        self._layer = int(_layer)

    @console_command
    def setLightSourceMask(self, light_source_mask):
        self.light_source_mask = int(light_source_mask)

    def make_script(self):
        s = f'Object.create {self.template.name.lower()}\n'
        if self.absolute_pos != (0, 0, 0):
            s += f'Object.absolutePosition {_vec_to_str(self.absolute_pos)}\n'
        if self.rot != (0, 0, 0):
            s += f'Object.rotation {_vec_to_str(self.rot)}\n'
        if self.transform:
            matrix_str = ""
            for row in self.transform:
                matrix_str += '[' + _vec_to_str(row) + ']'
            s += f'Object.absoluteTransformation {matrix_str}\n'
        if self._layer:
            s += f'Object.layer {self._layer}\n'
        if self.is_overgrowth:
            s += f'Object.isOvergrowth {int(self.is_overgrowth)}\n'
        if self.light_source_mask:
            s += f'Object.setLightSourceMask {self.light_source_mask}\n'
        s += f'\n'
        return s


class ObjectManager(Manager):
    MANAGED_TYPE = Object

    def __init__(self, engine=None):
        super(ObjectManager, self).__init__(engine)
        self.objects = list()
        self.active_obj = None

    @console_command
    def create(self, template):
        obj_temp_manager = self.engine.get_manager(ObjectTemplate)

        temp = obj_temp_manager.templates.get(template.lower())
        if not temp:
            self.engine.main_console.report(f"ObjectTemplate definition not found")
            self.active_obj = None
            return

        new_object = Object(temp)
        self.objects.append(new_object)
        self.active_obj = new_object
        return new_object


class LightManager():

    def __init__(self):
        self.sun_dir = (0, 0, 0)

    @console_command
    def sunDirection(self, vec):
        self.sun_dir = _str_to_vec(vec, 3)


class Animation(Template):
    def __init__(self, path, engine=None):
        super(Animation, self).__init__(path)
        self.path = path
        self.looping = None
        self.length = None
        self.ignore_mother_orientation = None


class AnimationManager(TemplateManager):
    MANAGED_TYPE = Animation

    @console_command
    def createAnimation(self, path):
        self.create(path)

    @console_command
    def looping(self, val):
        self.active_obj.looping = bool(int(val))

    @console_command
    def length(self, val):
        self.active_obj.length = float(val)

    @console_command
    def ignoreMotherOrientation(self, bone_id):
        self.active_obj.ignore_mother_orientation = int(bone_id)


class BF2EngineException(Exception):
    pass


class BF2Engine():

    def __init__(self, silent=True):
        self.silent = silent
        self.reset()

    def reset(self):
        self.glob_managers = list()
        self.glob_managers.append(ObjectTemplateManager(self))
        self.glob_managers.append(GeometryTemplateManager(self))
        self.glob_managers.append(CollisionManager(self))
        self.glob_managers.append(ObjectManager(self))
        self.glob_managers.append(HeightmapClusterManager(self))
        self.glob_managers.append(AnimationManager(self))
        self.file_manager : FileManager = FileManager()
        self.light_manager : LightManager = LightManager()

        self.main_console : MainConsole = MainConsole(self, silent=self.silent)
        self.main_console.register_object(self.get_manager(ObjectTemplate), 'ObjectTemplate')
        self.main_console.register_object(self.get_manager(GeometryTemplate), 'GeometryTemplate')
        self.main_console.register_object(self.get_manager(Object), 'Object')
        self.main_console.register_object(self.get_manager(HeightmapCluster), 'HeightmapCluster')
        self.main_console.register_object(self.get_manager(HeightmapCluster), 'Heightmap')
        self.main_console.register_object(self.get_manager(CollisionMeshTemplate))
        animation_manager = self.get_manager(Animation)
        self.main_console.register_object(animation_manager, 'animationSystem')
        self.main_console.register_object(animation_manager, 'animationManager')
        self.main_console.register_object(self.file_manager)
        self.main_console.register_object(self.light_manager)

    def _get_manager(self, manager, _type):
        if not isinstance(manager, Manager):
            return None
        if _type == manager.MANAGED_TYPE:
            return manager
        # manager could be nested
        nested_manager = manager.active_obj
        if not nested_manager:
            return None
        if found := self._get_manager(nested_manager, _type):
            return found

    def get_manager(self, _type) -> Manager:
        for manager in self.glob_managers:
            if found := self._get_manager(manager, _type):
                return found
