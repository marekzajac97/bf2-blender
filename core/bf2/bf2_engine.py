import enum
import types
import os, glob, string
import os.path as path

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

    def __init__(self, silent = False):
        self._silent = silent
        self._active_root_con_file = None
        self._active_con_file = None
        self._processed_line = 0
        self._processed_directive = ''
        self._constants = {}
        self._variables = {}
        self._ignore = False
        self._registered_console_objects = dict()
    
    def register_object(self, cls):
        self._registered_console_objects[cls.__name__.lower()] = cls

    def get_active_con_file(self):
        return self._active_root_con_file

    def run_file(self, filepath, is_root=True, ignore_includes=False):
        f = ci_open(filepath, 'r')
        lines = f.readlines()
        f.close()

        if filepath is not None:
            filepath = filepath.replace('\\', '/').lstrip('/')

        if is_root:
            self._active_root_con_file = filepath
        self._active_con_file = filepath

        self._constants = {} # TODO: preserve scope on include
        self._variables = {}

        for line_no, line in enumerate(lines, start=1):
            self._processed_line = line_no
            self.exec(line, ignore_includes=ignore_includes)
        
        if is_root:
            self._active_root_con_file = None
        self._active_con_file = None

    def exec(self, line, ignore_includes=False):
        args = self._get_args(line)
        if not args: return
        
        op = args[0].lower()
        if op in ('endrem', 'endif'):
            self._ignore = False
            return
        if self._ignore or op == 'rem':
            return
        if op in ('beginrem', 'if'): # TODO: evaluate ifs?
            self._ignore = True
            return

        if op in ('run', 'include') and not ignore_includes:
            assert len(args) >= 2
            assert self._active_con_file is not None, 'missing base for include'

            _incfilepath = args[1].lstrip('\\/')
            basedir = path.dirname(self._active_con_file)

            p = path.join(basedir, _incfilepath)
            incpath = find_file(path.normpath(p))
            if incpath is None and basedir and not _incfilepath.startswith('.'):
                incpath = find_file(_incfilepath) # Maybe it's a full path (Objects/bla-bla-bla)?

            if incpath is None:
                pass # XXX
            else:
                con_file_backup = self._active_con_file
                self.run_file(incpath, is_root=False)
                self._active_con_file = con_file_backup
            
        self._process_directive(op, args[1:])
    
    def _execute_object_method(self, command, args):
        obj_name = command.split('.')[0].lower()
        method_name = '.'.join(command.split('.')[1:]).lower()

        obj_class = self._registered_console_objects.get(obj_name)

        obj_method = None
        try:
            obj_method = igetattr(obj_class, method_name)
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
                elif c_name.lower() in self._constants:
                    self.report('Attempted constant redefinition')
                else:
                    self._constants[c_name] = c_value
            
            elif command == 'var':
                if len(args) > 1 and args[1] == '=': # definition + assignment
                    v_value = args[2]
                else:              # definition only
                    v_value = ''
                v_name = args[0].lower()
                if not v_name.startswith('v_'):
                    self.report('Variable name not starting with "v_"')
                elif v_name.lower() in self._variables:
                    self.report('Attempted constant redefinition')
                else:
                    self._variables[v_name] = v_value
        except IndexError:
            self.report('Wrong syntax')
            return
        
        # TODO: variable assignements
        # TODO: replace args with consts/vars
        # TODO: while, return keywords??
        # TODO: variable assignmnets as con outputs with ->

        self._execute_object_method(command, args)
        self._processed_directive = ''

    def report(self, *what):
        if self._silent:
            return
        content = ' '.join(map(str, what))
        if self._active_con_file:
            print('{} | {}: "{}" {}'.format(self._active_con_file, self._processed_line, self._processed_directive, content))
        else:
            print(content)

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
            return 'Activating non exisiting template {}'.format(template)

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
