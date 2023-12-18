import struct

class FileUtils:
    def __init__(self, file):
        self.file = file
    
    def read_dword(self, signed=False):
        return int.from_bytes(self.file.read(4), "little", signed=signed)
    
    def read_float(self):
        return struct.unpack('f', self.file.read(4))[0]

    def read_word(self, signed=False):
        return int.from_bytes(self.file.read(2), "little", signed=signed)

    def read_byte(self, signed=False):
        return int.from_bytes(self.file.read(1), "little", signed=signed)

    def write_dword(self, content, signed=False):
        self.file.write(content.to_bytes(4, "little", signed=signed))
    
    def write_float(self, content):
        self.file.write(struct.pack('f', content))

    def write_word(self, content, signed=False):
        self.file.write(content.to_bytes(2, "little", signed=signed))

    def write_byte(self, content, signed=False):
        self.file.write(content.to_bytes(1, "little", signed=signed))