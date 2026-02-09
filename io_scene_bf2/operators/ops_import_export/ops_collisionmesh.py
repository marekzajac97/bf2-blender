import bpy # type: ignore
from bpy.props import StringProperty, BoolProperty # type: ignore
from bpy_extras.io_utils import poll_file_object_drop # type: ignore

from ..utils import RegisterFactory
from .ops_common import ImporterBase, ExporterBase

from ...core.collision_mesh import import_collisionmesh, export_collisionmesh
from ...core.utils import find_root, Reporter

class CollisionMeshMeta:
    FILE_DESC = "CollisionMesh (.collisionmesh)"

class IMPORT_OT_bf2_collisionmesh(bpy.types.Operator, ImporterBase, CollisionMeshMeta):
    bl_idname= "bf2.collisionmesh_import"
    bl_description = 'Battlefield 2 collision mesh file'
    bl_label = "Import Collision Mesh"
    filter_glob: StringProperty(default="*.collisionmesh", options={'HIDDEN'}) # type: ignore

    load_backfaces: BoolProperty(
        name="Backfaces",
        description="Adds 'backface' attribute to double-sided faces. Disabling this will ignore any duplicated faces",
        default=True
    ) # type: ignore

    def _execute(self, context):
        context.view_layer.objects.active = \
            import_collisionmesh(context,
                self.filepath,
                load_backfaces=self.load_backfaces,
                reporter=Reporter(self.report))


class EXPORT_OT_bf2_collisionmesh(bpy.types.Operator, ExporterBase, CollisionMeshMeta):
    bl_idname = "bf2.collisionmesh_export"
    bl_description = 'Battlefield 2 collision mesh file'
    bl_label = "Export Collision Mesh"

    filename_ext = ".collisionmesh"
    filter_glob: StringProperty(default="*.collisionmesh", options={'HIDDEN'}) # type: ignore

    save_backfaces: BoolProperty(
        name="Backfaces",
        description="Exports faces with 'backface' attribute as double-sided",
        default=True
    ) # type: ignore

    apply_modifiers: BoolProperty(
        name="Apply Modifiers",
        description="Apply object modifiers",
        default=True
    ) # type: ignore

    @classmethod
    def poll(cls, context):
        cls.poll_message_set("No object active")
        return context.view_layer.objects.active is not None

    def _execute(self, context):
        root = find_root(context.view_layer.objects.active)
        export_collisionmesh(root, self.filepath,
                             save_backfaces=self.save_backfaces,
                             apply_modifiers=self.apply_modifiers,
                             triangulate=True,
                             reporter=Reporter(self.report))

    def invoke(self, context, _event):
        root = find_root(context.view_layer.objects.active)
        self.filepath = root.name + self.filename_ext
        return super().invoke(context, _event)

class IMPORT_EXPORT_FH_collisionmesh(bpy.types.FileHandler):
    bl_idname = "IMPORT_EXPORT_FH_collisionmesh"
    bl_label = "BF2 CollisionMesh"
    bl_import_operator = IMPORT_OT_bf2_collisionmesh.bl_idname
    bl_export_operator = EXPORT_OT_bf2_collisionmesh.bl_idname
    bl_file_extensions = ".collisionmesh"

    @classmethod
    def poll_drop(cls, context):
        return poll_file_object_drop(context)

def init(rc : RegisterFactory):
    rc.reg_class(IMPORT_OT_bf2_collisionmesh)
    rc.reg_class(EXPORT_OT_bf2_collisionmesh)
    rc.reg_class(IMPORT_EXPORT_FH_collisionmesh)

register, unregister = RegisterFactory.create(init)