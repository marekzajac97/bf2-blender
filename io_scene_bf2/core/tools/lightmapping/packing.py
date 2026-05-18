import os
import os.path as path

import bpy
import numpy as np

from .... import rectpack
from ...utils import save_img_as_dds


def pack_lightmaps(input_dir, output_dir, level_path, dds_fmt='DXT1', atlas_size=(2048, 2048)):
    dds_files = []
    for file in sorted(os.listdir(input_dir)):
        filepath = path.join(input_dir, file)
        if not path.isfile(filepath):
            continue
        if not file.endswith('.dds'):
            continue
        dds_files.append(filepath)

    if not dds_files:
        return

    file_info = {}
    loaded_images = []
    for filepath in dds_files:
        fname = path.basename(filepath)
        img = bpy.data.images.load(filepath, check_existing=False)
        file_info[fname] = img
        loaded_images.append(img)

    packer = rectpack.newPacker(rotation=False)

    for fname, img in file_info.items():
        w, h = img.size
        packer.add_rect(w, h, fname)

    for _ in range(99):
        packer.add_bin(*atlas_size)

    packer.pack()

    atlas_entries = []

    for atlas_idx, bin in enumerate(packer):
        atlas_name = f'LightmapAtlas{atlas_idx}'
        atlas_img = bpy.data.images.new(atlas_name, atlas_size[0], atlas_size[1])
        atlas_pixels = np.zeros((atlas_size[1], atlas_size[0], 4), dtype=np.float32)

        for rect in bin:
            source_name = rect.rid
            source_img = file_info[source_name]

            w, h = source_img.size
            src_channels = source_img.channels
            src_pixels = np.array(source_img.pixels[:]).reshape((h, w, src_channels))

            y, x = rect.y, rect.x

            if src_channels == 4:
                atlas_pixels[y:y + h, x:x + w, :] = src_pixels
            elif src_channels == 3:
                atlas_pixels[y:y + h, x:x + w, :3] = src_pixels
                atlas_pixels[y:y + h, x:x + w, 3] = 1.0
            else:
                atlas_pixels[y:y + h, x:x + w, 0] = src_pixels[:, :, 0]
                atlas_pixels[y:y + h, x:x + w, 1] = src_pixels[:, :, 0]
                atlas_pixels[y:y + h, x:x + w, 2] = src_pixels[:, :, 0]
                atlas_pixels[y:y + h, x:x + w, 3] = 1.0

            atlas_entries.append((source_name, atlas_idx, atlas_name, x, y, w, h))

        atlas_img.pixels = atlas_pixels.ravel().tolist()
        atlas_img.update()
        save_img_as_dds(atlas_img, path.join(output_dir, f'{atlas_name}.dds'), dds_fmt)
        bpy.data.images.remove(atlas_img)

    for img in loaded_images:
        bpy.data.images.remove(img)

    txt_path = path.join(output_dir, 'LightmapAtlas.tai')
    with open(txt_path, 'w') as f:
        objects_dir = f'{level_path}/Lightmaps/Objects/'
        for source_name, atlas_idx, atlas_name, x, y, w, h in atlas_entries:
            x /= atlas_size[0]
            y /= atlas_size[1]
            w /= atlas_size[0]
            h /= atlas_size[1]
            f.write(f'{objects_dir}{source_name}\t\t{objects_dir}{atlas_name}, {atlas_idx}, {x}, {y}, {w}, {h}\n')
