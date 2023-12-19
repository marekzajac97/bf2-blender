import bpy
import traceback
from bpy.props import StringProperty
from bpy_extras.io_utils import ImportHelper

from ..core.skeleton import import_skeleton

class IMPORT_OT_bf2_skeleton(bpy.types.Operator, ImportHelper):
    bl_idname= "bf2_skeleton.import"
    bl_description = 'Battlefield 2 skeleton file'
    bl_label = "Import skeleton"
    filter_glob = StringProperty(default="*.ske", options={'HIDDEN'})

    def execute(self, context):
        try:
           import_skeleton(context, self.filepath)
        except Exception as e:
            self.report({"ERROR"}, traceback.format_exc())
        return {'FINISHED'}

FILE_DESC = "Skeleton (.ske)"

def draw_import(layout):
    layout.operator(IMPORT_OT_bf2_skeleton.bl_idname, text=FILE_DESC)

def draw_export(layout):
    pass

def register():
    bpy.utils.register_class(IMPORT_OT_bf2_skeleton)

def unregister():
    bpy.utils.unregister_class(IMPORT_OT_bf2_skeleton)