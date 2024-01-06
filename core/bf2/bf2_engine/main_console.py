import inspect
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