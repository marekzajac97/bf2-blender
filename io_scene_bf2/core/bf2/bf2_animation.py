from .bf2_common import Quat, Vec3
from .fileutils import FileUtils
import os
import functools

def float_16_to_32(word, precision):
    flt16_mult = 32767.0 / (1 << 15 - precision)
    if word > 32767:
        word -= 0xFFFF
    return (word / flt16_mult)

def float_32_to_16(f, precision):
    flt16_mult = 32767.0 / (1 << 15 - precision)
    word = int(flt16_mult * f)
    if word >= -32767 and word < 0:
        word += 0xFFFF
    return word

def rle_compress(array):
    MIN_RLE_BLOCK_SIZE = 5
    MAX_BLOCK_SIZE = 126 # this is max frames we can encode on 7 bits

    class RepeatingValue():
        def __init__(self, count, value):
            self.count = count
            self.value = value

    # group by value
    grouped = list()
    if len(array) > 0:
        count = 1
        value = array[0]
        for entry in array[1:]:
            if entry == value:
                count += 1
            else:
                grouped.append(RepeatingValue(count, value))
                count = 1
                value = entry
        
        grouped.append(RepeatingValue(count, value))
    
    class RleChunk:
        def __init__(self, rle=False, values=[]):
            self.rle = rle
            self.values = values
    
    # convert to list of RleChunk
    chunk_list = list()
    for chunk in grouped:
        values = [chunk.value] * chunk.count

        if chunk.count > MIN_RLE_BLOCK_SIZE:
            chunk_list.append(RleChunk(True, values))
            continue
        else: # chunk not big enough, append to previuos chunk
            if len(chunk_list) == 0:
                prev_chunk = None
            else:
                prev_chunk = chunk_list[-1]
            if prev_chunk is None or prev_chunk.rle:
                # if this is first chunk prev chunk was rle, make new chunk
                chunk_list.append(RleChunk(False, values))
            else:
                prev_chunk.values.extend(values)

    # check for too long chunks
    chunk_list_final = list()
    for chunk in chunk_list:
        if len(chunk.values) > MAX_BLOCK_SIZE:
            for i in range(0, len(chunk.values), MAX_BLOCK_SIZE):
                shrunk_values = chunk.values[i:i+MAX_BLOCK_SIZE]
                chunk_list_final.append(RleChunk(chunk.rle, shrunk_values))
        else:
            chunk_list_final.append(chunk)

    # just to be sure check if input length == output length
    def flat(l):
        return [item for sublist in l for item in sublist]
    if len(flat(list(map(lambda x: x.values, chunk_list_final)))) != len(array):
        raise Exception("RLE compression error")
    return chunk_list_final


class BF2AnimationException(Exception):
    pass


class BF2KeyFrame:
    def __init__(self, pos=Vec3(), rot=Quat()):
        self.rot = rot.copy()
        self.pos = pos.copy()

    def __repr__(self):
        return f"KeyFrame({id(self)}) pos: {self.pos} rot: {self.rot}"
    

class BF2Animation:
    def __init__(self, baf_file=None):
        self.bones = dict()
        self.frame_num = 0
        
        if baf_file is None:
            return
        
        with open(baf_file, "rb") as f:
            anim_data = FileUtils(f)
            version = anim_data.read_dword()
            if version != 4:
                raise BF2AnimationException(f"Unsupported .baf version {version}")
            
            bone_num = anim_data.read_word()

            bone_ids = list()
            for _ in range(bone_num):
                bone_id = anim_data.read_word()
                bone_ids.append(bone_id)
            
            self.frame_num = anim_data.read_dword()
            precision = anim_data.read_byte()

            for bone_id in bone_ids:
                self.bones[bone_id] = frames = [BF2KeyFrame() for _ in range(self.frame_num)]
                data_size = anim_data.read_word()

                for j in range(1,8):
                    cur_frame = 0
                    data_left = anim_data.read_word()
    
                    while data_left > 0:
                        head = anim_data.read_byte()
                        rle_compression = (head & 0x80) >> 7 # 1st bit
                        num_frames = head & 0x7F # rest (7 bits);
                        next_header = anim_data.read_byte()

                        bone_frame_num = cur_frame + num_frames - 1
                        if bone_frame_num >= self.frame_num:
                            raise BF2AnimationException(f"Corrupted .baf, frame number for bone {bone_id} ({bone_frame_num}) exceeds max: {self.frame_num}")
    
                        if rle_compression:
                            value = anim_data.read_word()
                        for _ in range(num_frames):
                            if not rle_compression:
                                value = anim_data.read_word()
    
                            if j == 1: frames[cur_frame].rot.x = -float_16_to_32(value, 15)
                            if j == 2: frames[cur_frame].rot.y = -float_16_to_32(value, 15)
                            if j == 3: frames[cur_frame].rot.z = -float_16_to_32(value, 15)
                            if j == 4: frames[cur_frame].rot.w =  float_16_to_32(value, 15)
                        
                            if j == 5: frames[cur_frame].pos.x = float_16_to_32(value, precision)
                            if j == 6: frames[cur_frame].pos.y = float_16_to_32(value, precision)
                            if j == 7: frames[cur_frame].pos.z = float_16_to_32(value, precision)
    
                            cur_frame += 1
                        
                        data_left -= next_header
            
            if os.fstat(f.fileno()).st_size != f.tell():
                raise BF2AnimationException("Corrupted .baf file? Reading finished and file pointer != filesize")
    
    def export(self, export_path):
        with open(export_path, "wb") as f:
            anim_data = FileUtils(f)
            anim_data.write_dword(4) # version
            anim_data.write_word(len(self.bones)); # bone_num

            for bone_id in self.bones.keys():
                anim_data.write_word(bone_id)

            anim_data.write_dword(self.frame_num)

            # find pos axis value furthest from 0 (it's usually the camera at Z = ~1.5)
            max_value_for_animation = 0
            for frames in self.bones.values():
                max_for_this_bone = functools.reduce(lambda prev, fr: max(prev, abs(fr.pos.x), abs(fr.pos.y), abs(fr.pos.z)), frames, 0)
                max_value_for_animation = max(max_value_for_animation, max_for_this_bone)

            # find max possible float precision
            precision = None
            for prec in reversed(range(1, 16)):
                max_range_for_prec = 2**(16 - prec)
                max_value_for_prec = max_range_for_prec - max_range_for_prec / 2
                if max_value_for_animation <= max_value_for_prec:
                    precision = prec
                    break
            else:
                raise BF2AnimationException(f"Animation position axis value out of range: {max_value_for_animation}")

            anim_data.write_byte(precision)

            for bone_id, frames in self.bones.items():
                if len(frames) > self.frame_num:
                    raise BF2AnimationException(f"cannot export baf, number of frames for bone {bone_id} "
                                                f" ({len(frames)}) exceeds frameNum: ({self.frame_num}")

                class DataBlocks:
                    def __init__(self):
                        self.blocks = list()
                        self.data_left = 0
                
                class DataBlock:
                    def __init__(self):
                        self.rle_compression = False
                        self.head = 0
                        self.next_header = 0
                        self.values = []
    
                # collect data
                streams = list()
                data_size = 0
                for j in range(1,8):
                    if j == 1: values = list(map(lambda fr: float_32_to_16(-fr.rot.x, 15), frames))
                    if j == 2: values = list(map(lambda fr: float_32_to_16(-fr.rot.y, 15), frames))
                    if j == 3: values = list(map(lambda fr: float_32_to_16(-fr.rot.z, 15), frames))
                    if j == 4: values = list(map(lambda fr: float_32_to_16( fr.rot.w, 15), frames))

                    if j == 5: values = list(map(lambda fr: float_32_to_16(fr.pos.x, precision), frames))
                    if j == 6: values = list(map(lambda fr: float_32_to_16(fr.pos.y, precision), frames))
                    if j == 7: values = list(map(lambda fr: float_32_to_16(fr.pos.z, precision), frames))
    
                    data_blocks = DataBlocks()
    
                    rle_chunks = rle_compress(values)

                    for chunk in rle_chunks:
                        data_block = DataBlock()
                        data_blocks.blocks.append(data_block)
    
                        data_block.rle_compression = chunk.rle
                        num_frames = len(chunk.values)
                        data_block.head = (data_block.rle_compression << 7) | num_frames
                        if data_block.rle_compression:
                            data_block.next_header = 2
                        else:
                            data_block.next_header = num_frames + 1
                        data_block.values = chunk.values
                        data_blocks.data_left += data_block.next_header
    
                    streams.append(data_blocks)
                    data_size += data_blocks.data_left

                # write data
                anim_data.write_word(data_size)
                for stream in streams:
                    anim_data.write_word(stream.data_left)
    
                    for data_block in stream.blocks:
                        anim_data.write_byte(data_block.head)
                        anim_data.write_byte(data_block.next_header)
    
                        if data_block.rle_compression:
                            anim_data.write_word(data_block.values[0])
                        else:
                            for data_block_val in data_block.values:
                                anim_data.write_word(data_block_val)
