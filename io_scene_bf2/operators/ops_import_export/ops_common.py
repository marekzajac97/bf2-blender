import bpy # type: ignore
import traceback
from bpy_extras.io_utils import ImportHelper, ExportHelper # type: ignore

from ..utils import RegisterFactory
from ...core.exceptions import ImportException, ExportException


class IMPORT_MT_bf2_submenu(bpy.types.Menu):
    bl_idname = "IMPORT_MT_bf2_submenu"
    bl_label = "Battlefield 2"

    DRAW_CALLBACKS = list()

    @classmethod
    def append(cls, draw_cb):
        cls.DRAW_CALLBACKS.append(draw_cb)

    @classmethod
    def remove(cls, draw_cb):
        cls.DRAW_CALLBACKS.remove(draw_cb)

    def draw(self, context):
        for cb in self.DRAW_CALLBACKS:
            cb(self.layout)

def menu_func_import(self, context):
    self.layout.menu(IMPORT_MT_bf2_submenu.bl_idname, text="BF2")

class EXPORT_MT_bf2_submenu(bpy.types.Menu):
    bl_idname = "EXPORT_MT_bf2_submenu"
    bl_label = "Battlefield 2"

    DRAW_CALLBACKS = list()

    @classmethod
    def append(cls, draw_cb):
        cls.DRAW_CALLBACKS.append(draw_cb)

    @classmethod
    def remove(cls, draw_cb):
        cls.DRAW_CALLBACKS.remove(draw_cb)

    def draw(self, context):
        for cb in self.DRAW_CALLBACKS:
            cb(self.layout)

def menu_func_export(self, context):
    self.layout.menu(EXPORT_MT_bf2_submenu.bl_idname, text="BF2")

# ------------------------------------------------------------------

class ImporterBase(ImportHelper):

    @classmethod
    def draw_callback(cls, layout):
        layout.operator(cls.bl_idname, text=cls.FILE_DESC)

    @classmethod
    def register(cls):
        IMPORT_MT_bf2_submenu.append(cls.draw_callback)

    @classmethod
    def unregister(cls):
        try:
            IMPORT_MT_bf2_submenu.remove(cls.draw_callback)
        except ValueError as e:
            print(cls, e)

    def abort(self, msg):
        raise ImportException(msg)

    def execute(self, context):
        try:
            self._execute(context)
            return {'FINISHED'}
        except ImportException as e:
            self.report({"ERROR"}, str(e))
            return {'CANCELLED'}
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
            return {'CANCELLED'}

    def _execute(self, context):
        pass

class ExporterBase(ExportHelper):

    @classmethod
    def draw_callback(cls, layout):
        layout.operator(cls.bl_idname, text=cls.FILE_DESC)

    @classmethod
    def register(cls):
        EXPORT_MT_bf2_submenu.append(cls.draw_callback)

    @classmethod
    def unregister(cls):
        try:
            EXPORT_MT_bf2_submenu.remove(cls.draw_callback)
        except ValueError as e:
            print(cls, e)

    def abort(self, msg):
        raise ExportException(msg)

    def execute(self, context):
        try:
            self._execute(context)
            self.report({"INFO"}, "Export complete")
            return {'FINISHED'}
        except ExportException as e:
            self.report({"ERROR"}, str(e))
            return {'CANCELLED'}
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
            return {'CANCELLED'}

    def _execute(self, context):
        pass

# ------------------------------------------------------------------

def init(rc : RegisterFactory):
    rc.reg_class(IMPORT_MT_bf2_submenu)
    rc.add_menu(bpy.types.TOPBAR_MT_file_import, menu_func_import)

    rc.reg_class(EXPORT_MT_bf2_submenu)
    rc.add_menu(bpy.types.TOPBAR_MT_file_export, menu_func_export)

register, unregister = RegisterFactory.create(init)
