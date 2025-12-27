import enum
import types
import os, glob, string
import os.path as path
import io
from zipfile import ZipFile

def icase(item):
    assert type(item) == str
    out = ''
    for x in item:
        if x in string.ascii_letters:
            out += '[%s%s]' % (x.upper(), x.lower())
        else:
            out += x
    return out

def _find_file_linux(fn):
    if path.isfile(fn): # Maybe, no further optimizations needed?
        return fn

    fn = fn.replace('\\', '/') # escape windows path backslashes
    fn = icase(fn)
    found = glob.glob(fn)
    if found and path.isfile(found[0]):
        return found[0]
    else:
        return None

def _ci_exists_linux(fn):
    return _find_file_linux(fn) is not None

def _ci_open_linux(fn, mode):
    try:
        return open(fn, mode)
    except OSError:
        pass
        
    real_fn = _find_file_linux(fn)
    if real_fn is None:
        raise OSError('%s file does not exist' % fn)

    return open(real_fn, mode)

def _find_file_windows(fn):
    if path.isfile(fn):
        return fn
    else:
        return None

def _ci_exists_windows(fn):
    return path.isfile(fn)

def _ci_open_windows(fn, mode):
    return open(fn, mode)

if os.name == 'nt':
    find_file = _find_file_windows
    ci_exists = _ci_exists_windows
    ci_open   = _ci_open_windows
else:
    find_file = _find_file_linux
    ci_exists = _ci_exists_linux
    ci_open   = _ci_open_linux

def igetattr(obj, attr):
    for a in dir(obj):
        if a.lower() == attr.lower():
            return getattr(obj, a)
    raise AttributeError()

class MainConsole():

    class StackFrame:
        def __init__(self, con_file):
            self._con_file = con_file
            self._constants = dict()
            self._variables = set()

    def __init__(self, silent = False):
        self._silent = silent
        self._stack = list()
        self._processed_line = 0
        self._processed_directive = ''
        self._ignore = False
        self._inside_comment = False
        self._registered_console_objects = dict()

    def register_object(self, cls):
        if cls.__class__ == type:
            self._registered_console_objects[cls.__name__.lower()] = cls
        else:
            self._registered_console_objects[cls.__class__.__name__.lower()] = cls

    def get_active_con_file(self):
        return self._stack[-1]._con_file if self._stack else None

    def run_file(self, filepath, is_root=True, ignore_includes=False, args=[]):
        try:
            content = BF2Engine().file_manager.readFile(filepath, is_root=is_root)
            lines = content.decode(errors='ignore').splitlines()
        except UnicodeDecodeError as e:
            print(filepath)
            raise
        except FileManagerFileNotFound as e:
            if not is_root:
                self.report('{} file not found'.format(filepath))
                return
            else:
                raise e

        filepath = filepath.replace('\\', '/').lstrip('/')
        self._stack.append(self.StackFrame(filepath))

        for i, arg in enumerate(args, start=1):
            self._stack[-1]._constants[f'v_arg{i}'] = arg

        for line_no, line in enumerate(lines, start=1):
            self._processed_line = line_no
            self.exec(line, ignore_includes)

        self._stack.pop()

    def exec(self, line, ignore_includes=False):
        args = self._get_args(line)
        if not args: return

        op = args[0].lower()
        if self._ignore:
            if op == 'endrem':
                self._ignore = self._inside_comment = False
            elif self._inside_comment:
                return
            else: # inside inactive branch
                if op == 'endif':
                    self._ignore = False
            return

        # check comment
        if self._inside_comment or op == 'rem':
            return
        if op == 'beginrem':
            self._inside_comment = True
            return

        # check branch
        if op in ('if', 'elseif'):
            self._ignore = not self._eval_condition(args[1:])
            return

        if op in ('run', 'include') and not ignore_includes:
            if len(args) < 2:
                return
            self.run_file(args[1], is_root=False, args=args[2:])
            return

        self._process_directive(op, args[1:])
    
    def _execute_object_method(self, command, args):
        obj_name = command.split('.')[0].lower()
        method_name = '.'.join(command.split('.')[1:]).lower()

        obj_class_or_instance = self._registered_console_objects.get(obj_name)

        obj_method = None
        try:
            obj_method = igetattr(obj_class_or_instance, method_name)
            if not callable(obj_method):
                obj_method = None
        except AttributeError:
            pass

        if not obj_method:
            self.report('Unknown object or method')
            return

        try:
            obj_method(*args)
        except TypeError:
            self.report('invalid argument arity')

    def _get_args(self, line):
        if '"' not in line:
            return line.split()
            
        out = []
        is_quoted = False
        for part in line.strip().split('"'):
            if is_quoted:
                out.append(part)
                is_quoted = False
            else:
                out += part.split()
                is_quoted = True

        if out and not is_quoted and out[0].lower() != 'rem':
            self.report("'%s' command either is missing a closing quote or has an excess quote" % line.strip())

        return out

    def _process_directive(self, command, args):
        self._processed_directive = "%s %s" % (command, ' '.join(args))

        try:
            if command == 'const' and args[1] == '=':
                c_name = args[0].lower()
                c_value = args[2]
                if not c_name.startswith('c_'):
                    self.report('Constant name not starting with "c_"')
                elif c_name.lower() in self._stack[-1]._constants:
                    self.report('Attempted constant redefinition')
                else:
                    self._stack[-1]._constants[c_name] = c_value
            
            elif command == 'var':
                if len(args) > 1 and args[1] == '=': # definition + assignment
                    v_value = args[2]
                else:              # definition only
                    v_value = ''
                v_name = args[0].lower()
                if not v_name.startswith('v_'):
                    self.report('Variable name not starting with "v_"')
                elif v_name.lower() in self._stack[-1]._variables:
                    self.report('Attempted constant redefinition')
                else:
                    self._stack[-1]._variables[v_name] = v_value
        except IndexError:
            self.report('Wrong syntax')
            return
        
        # TODO: variable assignements
        # TODO: replace args with consts/vars
        # TODO: while, return keywords??
        # TODO: variable assignmnets as con outputs with ->

        self._execute_object_method(command, args)
        self._processed_directive = ''

    def _const_or_var(self, name):
        sf = self._stack[-1]
        if name in sf._constants:
            return sf._constants[name]
        elif name in sf._variables:
            sf._variables[name]

    def _eval_condition(self, args):
        if len(args) == 3:
            lhs = self._const_or_var(args[0]) or args[0]
            rhs = self._const_or_var(args[2]) or args[2]
            if not lhs or not rhs:
                return False
            op = args[1].lower()
            if op in ('equals', '=='):
                return lhs == rhs
            if op in ('notequals', '!='):
                return lhs == rhs
            # TODO: support non-string operations
        else:
            return False # TODO: support logical operators or/and etc

    def report(self, *what):
        if self._silent:
            return
        content = ' '.join(map(str, what))
        print('{} | {}: "{}" {}'.format(self.get_active_con_file(), self._processed_line, self._processed_directive, content))

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
        active = BF2Engine().get_manager(objtype or type(obj)).active_obj
        if active:
            return types.MethodType(self.func, active)

        def not_active_dummy(*args, **kwargs):
            return 'Template not active'
        return not_active_dummy

def instancemethod(func):
    return InstanceMethod(func)

class Manager:
    def __init__(self):
        self.active_obj = None

    def get_nested_manager(self, _type):
        return None

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


class TemplateManager(Manager):
    MANAGED_TYPE = Template

    def __init__(self):
        self.templates = dict()
        self.active_obj = None

    def create(self, *args):
        new_template = self.MANAGED_TYPE(*args)
        name = new_template.name.lower()
        if name in self.templates:
            template = self.templates[name]
            self.active_obj = template
            return None
        self.templates[name] = new_template
        self.active_obj = new_template
        return new_template

    def active(self, template):
        template_low = template.lower()
        temp = self.templates.get(template_low)
        if temp:
            self.active_obj = temp
        else:
            self.active_obj = None
            BF2Engine().main_console.report('Activating non exisiting template {}'.format(template))


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
        self.anchor_point = None

    def add_bundle_childs(self):
        mngr = BF2Engine().get_manager(self.__class__)
        for child in self.children:
            child.template = mngr.templates.get(child.template_name.lower())
            if child.template:
                child.template.parent = self
                child.template.add_bundle_childs()
            else:
                BF2Engine().main_console.report(f"add_bundle_childs: ObjectTemplate {child.template} not found")

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
        BF2Engine().get_manager(cls).activeSafe(*args)

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
        if val.isdigit():
            self.physics_type = ObjectTemplate._PhysicsType(int(val))
        else:
            self.physics_type = ObjectTemplate._PhysicsType[val.upper()]

    @instancemethod
    def creator(self, val):
        self.creator_name = val

    @instancemethod
    def saveInSeparateFile(self, val):
        self.save_in_separate_file = bool(val)

    @instancemethod
    def anchor(self, vec):
        self.anchor_point = _str_to_vec(vec, 3)

class ObjectTemplateManager(TemplateManager):
    MANAGED_TYPE = ObjectTemplate

    def activeSafe(self, object_type, template):
        temp = self.active(template)
        if temp and temp.type.lower() != object_type.lower():
            self.active_obj = None

    def add_bundle_childs(self, object_template):
        for child in object_template.children:
            child.template = self.templates[child.template_name.lower()]
            child.template.parent = object_template
            self.add_bundle_childs(child.template)


class GeometryTemplate(Template):

    TYPES = {
        'staticmesh': 'StaticMesh',
        'bundledmesh': 'BundledMesh',
        'skinnedmesh': 'SkinnedMesh',
        'meshparticlemesh': 'MeshParticleMesh',
        'roadcompiled': 'RoadCompiled',
        'debugspheremesh': 'DebugSphereMesh'
    }

    def __init__(self, geometry_type, name):
        super(GeometryTemplate, self).__init__(name)
        if geometry_type.lower() in self.TYPES:
            self.geometry_type = self.TYPES[geometry_type.lower()]
        else:
            raise ValueError(f"Unknown geometry type {geometry_type}")

        self.nr_of_animated_uv_matrix = 0

        dir = os.path.dirname(BF2Engine().main_console.get_active_con_file().lower())
        self.location = os.path.join(dir, 'Meshes', f'{name}.{geometry_type.lower()}')

    def make_script(self, f):
        f.write(f'GeometryTemplate.create {self.geometry_type} {self.name}\n')
        if self.nr_of_animated_uv_matrix:
            f.write(f'GeometryTemplate.nrOfAnimatedUVMatrix {self.nr_of_animated_uv_matrix}\n')


class GeometryTemplateManager(TemplateManager):
    MANAGED_TYPE = GeometryTemplate


class CollisionMeshTemplate(Template):
    def __init__(self, name):
        super(CollisionMeshTemplate, self).__init__(name)
        dir = os.path.dirname(BF2Engine().main_console.get_active_con_file().lower())
        self.location = os.path.join(dir, 'Meshes', f'{name}.collisionmesh')

    def make_script(self, f):
        f.write(f'CollisionManager.createTemplate {self.name}\n')


class CollisionManager(TemplateManager):
    MANAGED_TYPE = CollisionMeshTemplate

    @classmethod
    def createTemplate(cls, name):
        self = BF2Engine().get_manager(cls.MANAGED_TYPE)
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

    @instancemethod
    def setSize(self, x, y):
        self.size = (int(x), int(y))

    @instancemethod
    def setScale(self, vec):
        self.scale = _str_to_vec(vec, 3)

    @instancemethod
    def setBitResolution(self, val):
        self.bit_res = int(val)

    @instancemethod
    def setMaterialScale(self, val):
        self.material_scale = float(val)

    @instancemethod
    def loadHeightData(self, val):
        self.raw_file = val

    @instancemethod
    def loadMaterialData(self, val):
        self.mat_file = val


class HeightmapCluster(Manager):
    MANAGED_TYPE = Heightmap

    def __init__(self, name):
        self.name = name # maybe its type?
        # TODO find defaults
        self.cluster_size = None
        self.heightmap_size = None
        self.heightmaps = list()
        self.active_obj = None
        self.water_level = 0

    @classmethod
    def create(cls, *args):
        BF2Engine().get_manager(HeightmapCluster).create(*args)

    @instancemethod
    def setClusterSize(self, size):
        self.cluster_size = int(size)

    @instancemethod
    def setHeightmapSize(self, size):
        self.heightmap_size = int(size)

    @instancemethod
    def addHeightmap(self, _type, offset_x, offset_z):
        self.active_obj = Heightmap(_type, int(offset_x), int(offset_z))
        self.heightmaps.append(self.active_obj)

    @instancemethod
    def setSeaWaterLevel(self, val):
        self.water_level = float(val)

class HeightmapClusterManager(Manager):
    MANAGED_TYPE = HeightmapCluster

    def __init__(self):
        self.reset()

    def get_nested_manager(self, _type):
        if _type == HeightmapCluster.MANAGED_TYPE:
            return self.active_obj

    def reset(self):
        self.clusters = list()
        self.active_obj = None

    def create(self, name):
        new_cluster = HeightmapCluster(name)
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

    @classmethod
    def create(cls, *args):
        BF2Engine().get_manager(Object).create(*args)

    @instancemethod
    def isOvergrowth(self, flag):
        self.is_overgrowth = bool(flag)

    @instancemethod
    def absolutePosition(self, pos):
        self.absolute_pos = _str_to_vec(pos, 3)

    @instancemethod
    def absoluteTransformation(self, matrix_str):
        self.transform = list()
        for row in matrix_str.strip('[]').split(']['):
            self.transform.append(_str_to_vec(row, 4))

    @instancemethod
    def rotation(self, rot):
        self.rot = _str_to_vec(rot, 3)
    
    @instancemethod
    def layer(self, _layer):
        self._layer = int(_layer)

    @instancemethod
    def setLightSourceMask(self, light_source_mask):
        self.light_source_mask = int(light_source_mask)

    def makeScript(self):
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

    def __init__(self):
        self.reset()

    def reset(self):
        self.objects = list()
        self.active_obj = None

    def create(self, template):
        obj_temp_manager = BF2Engine().get_manager(ObjectTemplate)

        temp = obj_temp_manager.templates.get(template.lower())
        if not temp:
            BF2Engine().main_console.report(f"ObjectTemplate does not exitst")
            return
            # raise ValueError(f"Object.create {template}, ObjectTemplate does not exitst")

        new_object = Object(temp)
        self.objects.append(new_object)
        self.active_obj = new_object
        return new_object


class FileManagerFileNotFound(Exception):
    pass


class FileManager:

    def __init__(self, root_dir='./'):
        self.root_dir = root_dir
        self._archive_to_zip = dict()
        self._mounted_archives = dict()
        self._mounted_paths = dict()

        self._current_dir = None
        self._current_dir_archive = None
        self._current_dir_path = None
    
    def __del__(self):
        for _, archive in self._archive_to_zip.items():
            archive.close()
    
    def getZipFile(self, archive):
        archive = archive.lower()
        return self._archive_to_zip[archive]

    def getArchives(self, mount_dir=''):
        if mount_dir:
            if mount_dir in self._mounted_archives:
                return self._mounted_archives[mount_dir]
            else:
                return []
        else:
            return [item for _, v in self._mounted_archives.items() for item in v]
    
    def getPaths(self, mount_dir=''):
        if mount_dir:
            if mount_dir in self._mounted_paths:
                return self._mounted_paths[mount_dir]
            else:
                return []
        else:
            return [item for _, v in self._mounted_paths.items() for item in v]

    def findInArchive(self, archive, fn):
        try:
            self._archive_to_zip[archive].getinfo(fn) # try hashset search first
            return fn
        except KeyError:
            pass
        for f in self._archive_to_zip[archive].namelist():
            if f.lower() == fn.lower():
                return f
        return None

    def readFile(self, *args, as_stream=False, **kwargs):
        content = self._readFile(*args, **kwargs)
        if as_stream:
            return io.BytesIO(content)
        return content

    def _readFile(self, filepath, is_root=True):

        if is_root:
            self._current_dir = None
            self._current_dir_archive = None
            self._current_dir_path = None

        filepath = filepath.replace('\\', '/').lstrip('/')

        # check if it's relative path first
        if self._current_dir:
            if self._current_dir_archive:
                real_path = path.normpath(path.join(self._current_dir, filepath)).replace('\\', '/')
                archived_fname = self.findInArchive(self._current_dir_archive, real_path)
                if archived_fname is not None:
                    content = self._archive_to_zip[self._current_dir_archive].read(archived_fname)
                    self._current_dir = path.dirname(real_path)
                    return content
            else:
                real_path = _fpath = path.join(self._current_dir, filepath)
                if self._current_dir_path:
                    real_path = path.normpath(path.join(self._current_dir_path, _fpath))
                _file = find_file(real_path)
                if _file:
                    f = ci_open(_file, 'rb')
                    self._current_dir = path.dirname(_fpath).replace('\\', '/')
                    content = f.read()
                    f.close()
                    return content

        # check if absolute path: e.g. objects/blah/../blah

        for mount_dir, archives in self._mounted_archives.items():
            if filepath.lower().startswith(mount_dir):
                fpath = filepath[len(mount_dir):][1:]
                for archive in archives:                    
                    archived_fname = self.findInArchive(archive, fpath)
                    if archived_fname is not None:
                        content = self._archive_to_zip[archive].read(archived_fname)
                        self._current_dir = path.dirname(fpath)
                        self._current_dir_archive = archive
                        self._current_dir_path = None
                        return content
                break

        for mount_dir, paths in self._mounted_paths.items():
            if filepath.lower().startswith(mount_dir):
                fpath = filepath[len(mount_dir):][1:]
                for _path in paths:
                    _file = find_file(path.join(_path, fpath))
                    if not _file:
                        continue
                    
                    f = ci_open(_file, 'rb')
                    self._current_dir = path.dirname(fpath)
                    self._current_dir_archive = None
                    self._current_dir_path = _path
                    content = f.read()
                    f.close()
                    return content
                break

        # check is outside of zip
        abspath = os.path.join(BF2Engine().file_manager.root_dir, filepath)
        if os.path.isfile(abspath):
            self._current_dir = path.dirname(abspath)
            self._current_dir_archive = None
            self._current_dir_path = None
            f = ci_open(abspath, 'rb')
            content = f.read()
            f.close()
            return content

        raise FileManagerFileNotFound("{} not found".format(filepath))

    def mountPath(self, dirpath, mount_dir):
        dirpathfull = path.join(self.root_dir, dirpath)
        if not path.isdir(dirpathfull):
            return
        # print('[FileManager] Mounting path {}'.format(dirpathfull))
        k = mount_dir.lower()
        if k not in self._mounted_paths:
            self._mounted_paths[k] = list()
        self._mounted_paths[k].append(dirpathfull)

    def mountArchive(self, archive, mount_dir, mode='r'):
        archive = archive.lower()
        zipfullpath = find_file(path.join(self.root_dir, archive))
        if not zipfullpath:
            return
        # print('[FileManager] Mounting archive {}'.format(archive))
        k = mount_dir.lower()
        if k not in self._mounted_archives:
            self._mounted_archives[k] = list()
        self._mounted_archives[k].append(archive)
        self._archive_to_zip[archive] = ZipFile(zipfullpath, mode) # keep zips open for better performance

    def unmountArchive(self, archive):
        zip = self._archive_to_zip[archive]
        zip.close()
        del self._archive_to_zip[archive]
        for archives in self._mounted_archives.values():
            if archive in archives:
                archives.remove(archive)
                break
        return

    def unmoutAll(self):
        for zip in self._archive_to_zip.values():
            zip.close()
        self._archive_to_zip.clear()
        self._mounted_archives.clear()


class BF2Engine():
    _instance = None

    def get_manager(self, _type) -> Manager:
        for manager in self.singletons:
            if _type == manager.MANAGED_TYPE:
                return manager
            elif nm := manager.get_nested_manager(_type):
                return nm

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls._instance, cls):
            cls._instance = object.__new__(cls, *args, **kwargs)
            cls._instance.init()
        return cls._instance

    def init(self):
        self.singletons = list()
        self.singletons.append(ObjectTemplateManager())
        self.singletons.append(GeometryTemplateManager())
        self.singletons.append(CollisionManager())
        self.singletons.append(ObjectManager())
        self.singletons.append(HeightmapClusterManager())
        self.file_manager : FileManager = FileManager()
        self.main_console : MainConsole = MainConsole(silent=True)
        self.main_console.register_object(ObjectTemplate)
        self.main_console.register_object(GeometryTemplate)
        self.main_console.register_object(CollisionManager)
        self.main_console.register_object(Object)
        self.main_console.register_object(HeightmapCluster)
        self.main_console.register_object(Heightmap)
        self.main_console.register_object(self.file_manager)

    @classmethod
    def shutdown(cls):
        cls._instance = None
