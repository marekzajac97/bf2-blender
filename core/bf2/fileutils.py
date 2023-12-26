import struct

class FileUtils:
    def __init__(self, file):
        self.file = file

    def _read(self, data_type, count=1, signed=False):
        dt = data_type.lower() if signed else data_type
        fmt =  f'{count}{dt}'
        size = struct.calcsize(fmt)
        unpacked = struct.Struct(fmt).unpack(self.file.read(size))          
        if count == 1:
            return unpacked[0]
        else:
            return unpacked

    def _write(self, content, data_type, count=1, signed=False):
        fmt = str(count) + data_type.lower() if signed else data_type
        if count == 1:
            packed = struct.Struct(fmt).pack(content)
        else:
            packed = struct.Struct(fmt).pack(*content)
        self.file.write(packed)

    def read_byte(self, count=1, signed=False):
        return self._read('B', count=count, signed=signed)

    def read_word(self, count=1, signed=False):
        return self._read('H', count=count, signed=signed)

    def read_dword(self, count=1, signed=False):
        return self._read('I', count=count, signed=signed)

    def read_float(self, count=1):
        return self._read('f', count=count)

    def read_string(self):
        lenght = self.read_dword()
        unpacked = struct.Struct(f'{lenght}s').unpack(self.file.read(lenght))
        return unpacked[0].decode('ascii')

    def read_raw(self, lenght=1):
        return self.file.read(lenght)

    def write_byte(self, content, count=1, signed=False):
        self.write('B', content, count=count, signed=signed)

    def write_word(self, content, count=1, signed=False):
        self.write('H', content, count=count, signed=signed)

    def write_dword(self, content, count=1, signed=False):
        self.write('I', content, count=count, signed=signed)
    
    def write_float(self, content, count=1, signed=False):
        self.write('I', content, count=count, signed=signed)

    def write_string(self, content):
        lenght = len(content)
        self.write_long(lenght)
        self.file.write(struct.Struct(f'{lenght}s').pack(content))

    def write_raw(self, content):
        self.file.write(content)