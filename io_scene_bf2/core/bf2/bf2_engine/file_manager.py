import os, glob, string
import os.path as path
from zipfile import ZipFile
import io

from .common import console_command

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

class FileManagerFileNotFound(Exception):
    pass

class FileManager:

    def __init__(self, root_dirs=['./']):
        self.root_dirs = root_dirs
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

        filepath = filepath.replace('\\', '/').rstrip('/')

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
        for root_dir in self.root_dirs:
            abspath = os.path.join(root_dir, filepath)
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
        for root_dir in self.root_dirs:
            dirpathfull = path.join(root_dir, dirpath)
            if not path.isdir(dirpathfull):
                continue
            # print('[FileManager] Mounting path {}'.format(dirpathfull))
            k = mount_dir.lower()
            if k not in self._mounted_paths:
                self._mounted_paths[k] = list()
            self._mounted_paths[k].append(dirpathfull)
            break

    @console_command
    def mountArchive(self, archive, mount_dir, mode='r'):
        archive = archive.lower()
        for root_dir in self.root_dirs:
            zipfullpath = find_file(path.join(root_dir, archive))
            if not zipfullpath:
                continue
            # print('[FileManager] Mounting archive {}'.format(archive))
            k = mount_dir.lower()
            if k not in self._mounted_archives:
                self._mounted_archives[k] = list()
            self._mounted_archives[k].append(archive)
            self._archive_to_zip[archive] = ZipFile(zipfullpath, mode) # keep zips open for better performance
            break

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
