import re
import os

def unplug_socket_from(material, socket_name, node_type='BSDF_PRINCIPLED'):
    if not material.is_bf2_material:
        return None
    node_tree = material.node_tree
    for node_link in node_tree.links:
        node = node_link.to_node
        if node.type == node_type and node_link.to_socket.name == socket_name:
            from_socket = node_link.from_socket
            node_tree.links.remove(node_link)
            return from_socket

def plug_socket_to(material, socket_name, from_socket, node_type='BSDF_PRINCIPLED'):
    if not material.is_bf2_material:
        return
    node_tree = material.node_tree
    for node in node_tree.nodes:
        if node.type == node_type:
            node_socket = node.inputs[socket_name]
            material.node_tree.links.new(from_socket, node_socket)

def gen_lm_key(geom_template_name, position, lod):
    x, y, z = [str(int(i)) for i in position]
    return '='.join([geom_template_name.lower(), f'{lod:02d}', x, z, y])
