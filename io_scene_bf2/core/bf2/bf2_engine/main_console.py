import inspect

from .file_manager import FileManagerFileNotFound

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
            self._variables = dict()

    def __init__(self, engine, silent = False):
        self.engine = engine
        self._silent = silent
        self._stack = list()
        self._processed_line = 0
        self._processed_directive = ''
        self._ignore = False
        self._inside_comment = False
        self._registered_console_objects = dict()
        self.report_cb = None

    def register_object(self, obj, name=None):
        if name is None:
            name = obj.__name__ if obj.__class__ == type else obj.__class__.__name__
        self._registered_console_objects[name.lower()] = obj

    def get_active_con_file(self):
        return self._stack[-1]._con_file if self._stack else None

    def run_file(self, filepath, is_root=True, ignore_includes=False, args=[]):
        try:
            content = self.engine.file_manager.readFile(filepath, is_root=is_root)
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

        filepath = filepath.replace('\\', '/').rstrip('/')
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
        if op == 'rem':
            return
        if op == 'beginrem':
            self._ignore = self._inside_comment = True
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
        obj_name = command.split('.')[0]
        method_name = '.'.join(command.split('.')[1:])

        obj_class_or_instance = self._registered_console_objects.get(obj_name.lower())

        if not obj_class_or_instance:
            self.report('Unknown object')
            return

        obj_method = None
        try:
            obj_method = igetattr(obj_class_or_instance, method_name)
            if not callable(obj_method) or not getattr(obj_method, '_console_callable', False):
                obj_method = None
        except AttributeError:
            pass

        if not obj_method:
            self.report('Unknown method')
            return

        try:
            sig = inspect.signature(obj_method)
            sig.bind(*args)
        except TypeError as e:
            self.report('Invalid argument arity')
            return

        try:
            obj_method(*args)
        except TypeError as e:
            self.report(f'Failed to execute {command}: {e}')
            return

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

        try:
            self._execute_object_method(command, args)
        except ValueError:
            self.report('Wrong syntax')
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
        content = ' '.join(map(str, what))
        if self.report_cb:
            self.report_cb(self.get_active_con_file(), self._processed_line, self._processed_directive, content)
        if self._silent:
            return
        print('{} | {}: "{}" {}'.format(self.get_active_con_file(), self._processed_line, self._processed_directive, content))
