import pickle
import os
import hashlib
from typing import Dict, List
from .bf2.bf2_engine import (BF2Engine,
                            ObjectTemplate,
                            CollisionMeshTemplate,
                            GeometryTemplate)

CACHE_FILE_NAME = ".io_scene_bf2_cache"
CACHE_VERSION = "1.0" # must be changed if anything within xxxTemplate data is added/modified

class ModLoader:
    def __init__(self, mod_dir, level_name, use_cache=True):
        self.mod_dir = mod_dir
        self.level_name = level_name
        self.use_cache = use_cache

    def reload_all(self):
        BF2Engine().shutdown()
        file_manager = BF2Engine().file_manager
        main_console = BF2Engine().main_console

        file_manager.root_dir = self.mod_dir
        main_console.run_file('serverarchives.con')

        # cache mod objects
        if self.load_cache():
            return
        self.load_objects()
        self.write_cache()

    def load_cache_from_file(self, cache):
        with open(cache,'rb') as f:
            cache_data = pickle.load(f)
        objects = cache_data["objects"]
        geometries = cache_data["geometries"]
        collisons = cache_data["collisons"]

        obj_manager = BF2Engine().get_manager(ObjectTemplate)
        geom_manager = BF2Engine().get_manager(GeometryTemplate)
        col_manager = BF2Engine().get_manager(CollisionMeshTemplate)

        # TODO: make methods int TemplateManager for this
        objects.update(obj_manager.templates) # XXX so templates already exisiting don't get overwriten
        obj_manager.templates = objects

        geometries.update(geom_manager.templates)
        geom_manager.templates = geometries

        collisons.update(col_manager.templates)
        col_manager.templates = collisons

    def load_cache(self):
        file_manager = BF2Engine().file_manager
        if not self.use_cache:
            return False
        md5hash = self.object_archives_md5()
        for f in os.listdir(file_manager.root_dir):
            filepath = os.path.join(file_manager.root_dir, f)
            if f.startswith(CACHE_FILE_NAME) and os.path.isfile(filepath):
                cache_md5 = f.split('__')[-1]
                version_num = f.split('__')[-2]
                if CACHE_VERSION != version_num or md5hash != cache_md5:
                    os.remove(filepath)
                    continue
                self.load_cache_from_file(filepath)
                return True
        return False
    
    def object_archives_md5(self):
        file_manager = BF2Engine().file_manager
        hash_md5 = hashlib.md5()
        for zipfile in file_manager.getArchives('objects'):
            zipfile = zipfile.lower()
            zipfilepath = os.path.join(file_manager.root_dir, zipfile)
            with open(zipfilepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def write_cache_to_file(self, cache):
        obj_manager = BF2Engine().get_manager(ObjectTemplate)
        geom_manager = BF2Engine().get_manager(GeometryTemplate)
        col_manager = BF2Engine().get_manager(CollisionMeshTemplate)

        obj_templates = obj_manager.templates
        geom_templates = geom_manager.templates
        col_templates = col_manager.templates

        new_cache_data = {'objects': obj_templates, 'geometries': geom_templates, 'collisons': col_templates}

        with open(cache, 'wb') as outfile:
            pickle.dump(new_cache_data, outfile)

    def write_cache(self):
        if not self.use_cache:
            return False
        file_manager = BF2Engine().file_manager
        md5hash = self.object_archives_md5()
        filepath = os.path.join(file_manager.root_dir, CACHE_FILE_NAME + '__' + CACHE_VERSION + '__' + md5hash)
        self.write_cache_to_file(filepath)

    def load_objects(self, levels_only=False):
        file_manager = BF2Engine().file_manager
        main_console = BF2Engine().main_console

        files_to_process : Dict[List[str]] = dict()
        processed_con_files = set()

        for zipfile in file_manager.getArchives('objects'):
            zipfile = zipfile.lower()
            if levels_only and 'levels/' not in zipfile:
                continue
            zipObj = file_manager.getZipFile(zipfile)
            files_to_process[zipfile] = [f for f in zipObj.namelist() if f.endswith('.con') and f not in processed_con_files]
            processed_con_files.update(files_to_process[zipfile])

        for zipfile, files_to_process in files_to_process.items():
            zipObj = file_manager.getZipFile(zipfile)
            for file in files_to_process:
                main_console.run_file('objects/' + file)
