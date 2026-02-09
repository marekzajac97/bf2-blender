import traceback
from bpy_extras.io_utils import ImportHelper, ExportHelper # type: ignore

from ...core.exceptions import ImportException, ExportException

class ImporterBase(ImportHelper):

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
