import bpy # type: ignore

class Registrator():

    def on_register(self):
        ...
    
    def on_unregister(self):
        ...

class PropertyRegister(Registrator):

    def __init__(self, _type, attr, prop):
        self.type = _type
        self.attr = attr
        self.prop = prop

    def on_register(self):
        setattr(self.type, self.attr, self.prop)

    def on_unregister(self):
        delattr(self.type, self.attr)

class ClassRegister(Registrator):

    def __init__(self, clazz):
        self.clazz = clazz

    def on_register(self):
        bpy.utils.register_class(self.clazz)

    def on_unregister(self):
        bpy.utils.unregister_class(self.clazz)


class MenuAdd(Registrator):
    def __init__(self, menu_list, menu):
        self.menu_list = menu_list
        self.menu = menu

    def on_register(self):
        self.menu_list.append(self.menu)

    def on_unregister(self):
        self.menu_list.remove(self.menu)


class ModuleRegister(Registrator):
    def __init__(self, module):
        self.module = module

    def on_register(self):
        getattr(self.module, 'register')()

    def on_unregister(self):
        getattr(self.module, 'unregister')()

class RegisterFactory():

    @classmethod
    def create(cls, init_func):
        rc = cls()
        init_func(rc)
        return rc.apply()

    def __init__(self):
        self.registrators = list()

    def add_menu(self, menu_list, menu):
        self.registrators.append(MenuAdd(menu_list, menu))

    def reg_class(self, clazz):
        self.registrators.append(ClassRegister(clazz))

    def reg_prop(self, _type, attr, prop):
        self.registrators.append(PropertyRegister(_type, attr, prop))

    def reg_module(self, module):
        self.registrators.append(ModuleRegister(module))

    def apply(self):
        def register():
            for r in self.registrators:
                r.on_register()

        def unregister():
            for r in reversed(self.registrators):
                r.on_unregister()

        return register, unregister
