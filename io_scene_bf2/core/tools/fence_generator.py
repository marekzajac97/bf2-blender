import bpy # type: ignore

def make_objects_on_curve():
    if 'ObjectsOnCurve' in bpy.data.node_groups:
        return bpy.data.node_groups['ObjectsOnCurve']
    objectsoncurve_1 = bpy.data.node_groups.new(type='GeometryNodeTree', name="ObjectsOnCurve")

    objectsoncurve_1.color_tag = 'NONE'
    objectsoncurve_1.description = ""
    objectsoncurve_1.default_group_node_width = 140
    objectsoncurve_1.is_modifier = True
    objectsoncurve_1.show_modifier_manage_panel = True

    # objectsoncurve_1 interface

    # Socket Geometry
    geometry_socket = objectsoncurve_1.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    geometry_socket.attribute_domain = 'POINT'
    geometry_socket.default_input = 'VALUE'
    geometry_socket.structure_type = 'AUTO'

    # Socket Geometry
    geometry_socket_1 = objectsoncurve_1.interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    geometry_socket_1.attribute_domain = 'POINT'
    geometry_socket_1.default_input = 'VALUE'
    geometry_socket_1.structure_type = 'AUTO'

    # Socket Curve
    curve_socket = objectsoncurve_1.interface.new_socket(name="Curve", in_out='INPUT', socket_type='NodeSocketObject')
    curve_socket.attribute_domain = 'POINT'
    curve_socket.hide_in_modifier = True
    curve_socket.default_input = 'VALUE'
    curve_socket.structure_type = 'AUTO'

    # Socket Elements
    elements_socket = objectsoncurve_1.interface.new_socket(name="Elements", in_out='INPUT', socket_type='NodeSocketCollection')
    elements_socket.attribute_domain = 'POINT'
    elements_socket.hide_in_modifier = True
    elements_socket.default_input = 'VALUE'
    elements_socket.structure_type = 'AUTO'

    # Socket Realize Instances
    realize_instances_socket = objectsoncurve_1.interface.new_socket(name="Realize Instances", in_out='INPUT', socket_type='NodeSocketBool')
    realize_instances_socket.default_value = False
    realize_instances_socket.attribute_domain = 'POINT'
    realize_instances_socket.hide_in_modifier = True
    realize_instances_socket.default_input = 'VALUE'
    realize_instances_socket.structure_type = 'AUTO'

    # Initialize objectsoncurve_1 nodes

    # Node Group Input
    group_input = objectsoncurve_1.nodes.new("NodeGroupInput")
    group_input.name = "Group Input"

    # Node Group Output
    group_output = objectsoncurve_1.nodes.new("NodeGroupOutput")
    group_output.name = "Group Output"
    group_output.is_active_output = True

    # Node Instance on Points
    instance_on_points = objectsoncurve_1.nodes.new("GeometryNodeInstanceOnPoints")
    instance_on_points.name = "Instance on Points"
    # Selection
    instance_on_points.inputs[1].default_value = True
    # Pick Instance
    instance_on_points.inputs[3].default_value = True
    # Scale
    instance_on_points.inputs[6].default_value = (1.0, 1.0, 1.0)

    # Node Object Info
    object_info = objectsoncurve_1.nodes.new("GeometryNodeObjectInfo")
    object_info.name = "Object Info"
    object_info.transform_space = 'ORIGINAL'
    # As Instance
    object_info.inputs[1].default_value = False

    # Node Realize Instances
    realize_instances = objectsoncurve_1.nodes.new("GeometryNodeRealizeInstances")
    realize_instances.name = "Realize Instances"
    # Realize All
    realize_instances.inputs[2].default_value = True
    # Depth
    realize_instances.inputs[3].default_value = 0

    # Node Domain Size
    domain_size = objectsoncurve_1.nodes.new("GeometryNodeAttributeDomainSize")
    domain_size.name = "Domain Size"
    domain_size.component = 'INSTANCES'

    # Node Index
    index = objectsoncurve_1.nodes.new("GeometryNodeInputIndex")
    index.name = "Index"

    # Node Named Attribute
    named_attribute = objectsoncurve_1.nodes.new("GeometryNodeInputNamedAttribute")
    named_attribute.name = "Named Attribute"
    named_attribute.data_type = 'FLOAT_VECTOR'
    # Name
    named_attribute.inputs[0].default_value = "UV4"

    # Node Store Named Attribute
    store_named_attribute = objectsoncurve_1.nodes.new("GeometryNodeStoreNamedAttribute")
    store_named_attribute.name = "Store Named Attribute"
    store_named_attribute.data_type = 'FLOAT2'
    store_named_attribute.domain = 'CORNER'
    # Selection
    store_named_attribute.inputs[1].default_value = True
    # Name
    store_named_attribute.inputs[2].default_value = "UV4"

    # Node Vector Math
    vector_math = objectsoncurve_1.nodes.new("ShaderNodeVectorMath")
    vector_math.name = "Vector Math"
    vector_math.operation = 'ADD'

    # Node Capture Attribute.001
    capture_attribute_001 = objectsoncurve_1.nodes.new("GeometryNodeCaptureAttribute")
    capture_attribute_001.name = "Capture Attribute.001"
    capture_attribute_001.active_index = 0
    capture_attribute_001.capture_items.clear()
    capture_attribute_001.capture_items.new('FLOAT', "Float")
    capture_attribute_001.capture_items["Float"].data_type = 'INT'
    capture_attribute_001.domain = 'INSTANCE'

    # Node Combine XYZ
    combine_xyz = objectsoncurve_1.nodes.new("ShaderNodeCombineXYZ")
    combine_xyz.name = "Combine XYZ"
    # Z
    combine_xyz.inputs[2].default_value = 0.0

    # Node Vector Math.001
    vector_math_001 = objectsoncurve_1.nodes.new("ShaderNodeVectorMath")
    vector_math_001.label = "Normalize UVs"
    vector_math_001.name = "Vector Math.001"
    vector_math_001.hide = True
    vector_math_001.operation = 'DIVIDE'

    # Node Math.002
    math_002 = objectsoncurve_1.nodes.new("ShaderNodeMath")
    math_002.label = "Instance Index / Size"
    math_002.name = "Math.002"
    math_002.hide = True
    math_002.operation = 'DIVIDE'
    math_002.use_clamp = False

    # Node Math.003
    math_003 = objectsoncurve_1.nodes.new("ShaderNodeMath")
    math_003.label = "Normalize Instance Index"
    math_003.name = "Math.003"
    math_003.hide = True
    math_003.operation = 'DIVIDE'
    math_003.use_clamp = False

    # Node Math.004
    math_004 = objectsoncurve_1.nodes.new("ShaderNodeMath")
    math_004.name = "Math.004"
    math_004.hide = True
    math_004.operation = 'SQRT'
    math_004.use_clamp = False

    # Node Math.006
    math_006 = objectsoncurve_1.nodes.new("ShaderNodeMath")
    math_006.name = "Math.006"
    math_006.hide = True
    math_006.operation = 'TRUNC'
    math_006.use_clamp = False

    # Node Math.007
    math_007 = objectsoncurve_1.nodes.new("ShaderNodeMath")
    math_007.label = "Normalize Tile Index"
    math_007.name = "Math.007"
    math_007.hide = True
    math_007.operation = 'DIVIDE'
    math_007.use_clamp = False

    # Node Math.008
    math_008 = objectsoncurve_1.nodes.new("ShaderNodeMath")
    math_008.name = "Math.008"
    math_008.hide = True
    math_008.operation = 'CEIL'
    math_008.use_clamp = False

    # Node Math.010
    math_010 = objectsoncurve_1.nodes.new("ShaderNodeMath")
    math_010.label = "Apply X offset"
    math_010.name = "Math.010"
    math_010.hide = True
    math_010.operation = 'SUBTRACT'
    math_010.use_clamp = False

    # Node Transform Geometry.001
    transform_geometry_001 = objectsoncurve_1.nodes.new("GeometryNodeTransform")
    transform_geometry_001.name = "Transform Geometry.001"
    # Mode
    transform_geometry_001.inputs[1].default_value = 'Matrix'
    # Translation
    transform_geometry_001.inputs[2].default_value = (0.0, 0.0, 0.0)
    # Rotation
    transform_geometry_001.inputs[3].default_value = (0.0, 0.0, 0.0)
    # Scale
    transform_geometry_001.inputs[4].default_value = (1.0, 1.0, 1.0)

    # Node Instances to Points
    instances_to_points = objectsoncurve_1.nodes.new("GeometryNodeInstancesToPoints")
    instances_to_points.name = "Instances to Points"
    # Selection
    instances_to_points.inputs[1].default_value = True
    # Position
    instances_to_points.inputs[2].default_value = (0.0, 0.0, 0.0)
    # Radius
    instances_to_points.inputs[3].default_value = 0.05000000074505806

    # Node Capture Attribute.003
    capture_attribute_003 = objectsoncurve_1.nodes.new("GeometryNodeCaptureAttribute")
    capture_attribute_003.name = "Capture Attribute.003"
    capture_attribute_003.active_index = 1
    capture_attribute_003.capture_items.clear()
    capture_attribute_003.capture_items.new('FLOAT', "Position")
    capture_attribute_003.capture_items["Position"].data_type = 'FLOAT_VECTOR'
    capture_attribute_003.capture_items.new('FLOAT', "Rotation")
    capture_attribute_003.capture_items["Rotation"].data_type = 'QUATERNION'
    capture_attribute_003.domain = 'INSTANCE'

    # Node Instance Transform
    instance_transform = objectsoncurve_1.nodes.new("GeometryNodeInstanceTransform")
    instance_transform.name = "Instance Transform"

    # Node Separate Transform
    separate_transform = objectsoncurve_1.nodes.new("FunctionNodeSeparateTransform")
    separate_transform.name = "Separate Transform"

    # Node Store Named Attribute.001
    store_named_attribute_001 = objectsoncurve_1.nodes.new("GeometryNodeStoreNamedAttribute")
    store_named_attribute_001.name = "Store Named Attribute.001"
    store_named_attribute_001.data_type = 'FLOAT_VECTOR'
    store_named_attribute_001.domain = 'POINT'
    # Selection
    store_named_attribute_001.inputs[1].default_value = True
    # Name
    store_named_attribute_001.inputs[2].default_value = "instance_pos"

    # Node Store Named Attribute.002
    store_named_attribute_002 = objectsoncurve_1.nodes.new("GeometryNodeStoreNamedAttribute")
    store_named_attribute_002.name = "Store Named Attribute.002"
    store_named_attribute_002.data_type = 'QUATERNION'
    store_named_attribute_002.domain = 'POINT'
    # Selection
    store_named_attribute_002.inputs[1].default_value = True
    # Name
    store_named_attribute_002.inputs[2].default_value = "instance_rot"

    # Node Reroute
    reroute = objectsoncurve_1.nodes.new("NodeReroute")
    reroute.name = "Reroute"
    reroute.socket_idname = "NodeSocketGeometry"
    # Node Frame.001
    frame_001 = objectsoncurve_1.nodes.new("NodeFrame")
    frame_001.label = "tile lightmap UVs for each instance"
    frame_001.name = "Frame.001"
    frame_001.label_size = 20
    frame_001.shrink = True

    # Node Reroute.001
    reroute_001 = objectsoncurve_1.nodes.new("NodeReroute")
    reroute_001.name = "Reroute.001"
    reroute_001.hide = True
    reroute_001.socket_idname = "NodeSocketMatrix"
    # Node Group Output.001
    group_output_001 = objectsoncurve_1.nodes.new("NodeGroupOutput")
    group_output_001.name = "Group Output.001"
    group_output_001.is_active_output = False

    # Node Points to Vertices
    points_to_vertices = objectsoncurve_1.nodes.new("GeometryNodePointsToVertices")
    points_to_vertices.name = "Points to Vertices"
    # Selection
    points_to_vertices.inputs[1].default_value = True

    # Node Frame.002
    frame_002 = objectsoncurve_1.nodes.new("NodeFrame")
    frame_002.label = "export instance metadata as mesh attributes"
    frame_002.name = "Frame.002"
    frame_002.label_size = 20
    frame_002.shrink = True

    # Node Reroute.002
    reroute_002 = objectsoncurve_1.nodes.new("NodeReroute")
    reroute_002.name = "Reroute.002"
    reroute_002.socket_idname = "NodeSocketGeometry"
    # Node Self Object
    self_object = objectsoncurve_1.nodes.new("GeometryNodeSelfObject")
    self_object.name = "Self Object"

    # Node Object Info.001
    object_info_001 = objectsoncurve_1.nodes.new("GeometryNodeObjectInfo")
    object_info_001.name = "Object Info.001"
    object_info_001.transform_space = 'ORIGINAL'
    # As Instance
    object_info_001.inputs[1].default_value = False

    # Node Invert Matrix
    invert_matrix = objectsoncurve_1.nodes.new("FunctionNodeInvertMatrix")
    invert_matrix.name = "Invert Matrix"

    # Node Multiply Matrices
    multiply_matrices = objectsoncurve_1.nodes.new("FunctionNodeMatrixMultiply")
    multiply_matrices.name = "Multiply Matrices"

    # Node Collection Info
    collection_info = objectsoncurve_1.nodes.new("GeometryNodeCollectionInfo")
    collection_info.name = "Collection Info"
    collection_info.transform_space = 'ORIGINAL'
    # Separate Children
    collection_info.inputs[1].default_value = True
    # Reset Children
    collection_info.inputs[2].default_value = False

    # Node Remove Named Attribute.001
    remove_named_attribute_001 = objectsoncurve_1.nodes.new("GeometryNodeRemoveAttribute")
    remove_named_attribute_001.name = "Remove Named Attribute.001"
    # Pattern Mode
    remove_named_attribute_001.inputs[1].default_value = 'Exact'
    # Name
    remove_named_attribute_001.inputs[2].default_value = "instance_ref"

    # Node Group Input.002
    group_input_002 = objectsoncurve_1.nodes.new("NodeGroupInput")
    group_input_002.name = "Group Input.002"
    group_input_002.outputs[1].hide = True
    group_input_002.outputs[2].hide = True
    group_input_002.outputs[3].hide = True
    group_input_002.outputs[4].hide = True

    # Node For Each Geometry Element Input
    for_each_geometry_element_input = objectsoncurve_1.nodes.new("GeometryNodeForeachGeometryElementInput")
    for_each_geometry_element_input.name = "For Each Geometry Element Input"
    # Node For Each Geometry Element Output
    for_each_geometry_element_output = objectsoncurve_1.nodes.new("GeometryNodeForeachGeometryElementOutput")
    for_each_geometry_element_output.name = "For Each Geometry Element Output"
    for_each_geometry_element_output.active_generation_index = 1
    for_each_geometry_element_output.active_input_index = 1
    for_each_geometry_element_output.active_main_index = 0
    for_each_geometry_element_output.domain = 'POINT'
    for_each_geometry_element_output.generation_items.clear()
    for_each_geometry_element_output.generation_items.new('GEOMETRY', "Geometry")
    for_each_geometry_element_output.generation_items[0].domain = 'POINT'
    for_each_geometry_element_output.generation_items.new('ROTATION', "Rotation")
    for_each_geometry_element_output.generation_items[1].domain = 'POINT'
    for_each_geometry_element_output.input_items.clear()
    for_each_geometry_element_output.input_items.new('FLOAT', "Sample Point Tail")
    for_each_geometry_element_output.input_items.new('FLOAT', "Sample Point Head")
    for_each_geometry_element_output.inspection_index = 0
    for_each_geometry_element_output.main_items.clear()

    # Node Sample Curve.002
    sample_curve_002 = objectsoncurve_1.nodes.new("GeometryNodeSampleCurve")
    sample_curve_002.name = "Sample Curve.002"
    sample_curve_002.hide = True
    sample_curve_002.data_type = 'INT'
    sample_curve_002.mode = 'LENGTH'
    sample_curve_002.use_all_curves = True

    # Node Set Position
    set_position = objectsoncurve_1.nodes.new("GeometryNodeSetPosition")
    set_position.name = "Set Position"
    set_position.hide = True
    # Selection
    set_position.inputs[1].default_value = True
    # Offset
    set_position.inputs[3].default_value = (0.0, 0.0, 0.0)

    # Node Capture Attribute
    capture_attribute = objectsoncurve_1.nodes.new("GeometryNodeCaptureAttribute")
    capture_attribute.name = "Capture Attribute"
    capture_attribute.hide = True
    capture_attribute.active_index = 0
    capture_attribute.capture_items.clear()
    capture_attribute.capture_items.new('FLOAT', "Rotation")
    capture_attribute.capture_items["Rotation"].data_type = 'QUATERNION'
    capture_attribute.domain = 'POINT'

    # Node Align Rotation to Vector.004
    align_rotation_to_vector_004 = objectsoncurve_1.nodes.new("FunctionNodeAlignRotationToVector")
    align_rotation_to_vector_004.name = "Align Rotation to Vector.004"
    align_rotation_to_vector_004.hide = True
    align_rotation_to_vector_004.axis = 'Y'
    align_rotation_to_vector_004.pivot_axis = 'AUTO'
    # Rotation
    align_rotation_to_vector_004.inputs[0].default_value = (0.0, 0.0, 0.0)
    # Factor
    align_rotation_to_vector_004.inputs[1].default_value = 1.0

    # Node Mix.003
    mix_003 = objectsoncurve_1.nodes.new("ShaderNodeMix")
    mix_003.name = "Mix.003"
    mix_003.blend_type = 'MIX'
    mix_003.clamp_factor = True
    mix_003.clamp_result = False
    mix_003.data_type = 'VECTOR'
    mix_003.factor_mode = 'UNIFORM'

    # Node Sample Curve.003
    sample_curve_003 = objectsoncurve_1.nodes.new("GeometryNodeSampleCurve")
    sample_curve_003.name = "Sample Curve.003"
    sample_curve_003.hide = True
    sample_curve_003.data_type = 'INT'
    sample_curve_003.mode = 'LENGTH'
    sample_curve_003.use_all_curves = True

    # Node Reroute.007
    reroute_007 = objectsoncurve_1.nodes.new("NodeReroute")
    reroute_007.name = "Reroute.007"
    reroute_007.socket_idname = "NodeSocketGeometry"
    # Node Group Input.001
    group_input_001 = objectsoncurve_1.nodes.new("NodeGroupInput")
    group_input_001.name = "Group Input.001"
    group_input_001.outputs[0].hide = True
    group_input_001.outputs[1].hide = True
    group_input_001.outputs[2].hide = True
    group_input_001.outputs[4].hide = True

    # Node Compare
    compare = objectsoncurve_1.nodes.new("FunctionNodeCompare")
    compare.name = "Compare"
    compare.hide = True
    compare.data_type = 'INT'
    compare.mode = 'ELEMENT'
    compare.operation = 'EQUAL'

    # Node Switch
    switch = objectsoncurve_1.nodes.new("GeometryNodeSwitch")
    switch.name = "Switch"
    switch.input_type = 'FLOAT'
    # False
    switch.inputs[1].default_value = 1.0
    # True
    switch.inputs[2].default_value = 0.5

    # Node Curve of Point
    curve_of_point = objectsoncurve_1.nodes.new("GeometryNodeCurveOfPoint")
    curve_of_point.name = "Curve of Point"

    # Node Index.001
    index_001 = objectsoncurve_1.nodes.new("GeometryNodeInputIndex")
    index_001.name = "Index.001"

    # Node Frame.004
    frame_004 = objectsoncurve_1.nodes.new("NodeFrame")
    frame_004.label = "average both tangents but only if is on the same spline"
    frame_004.name = "Frame.004"
    frame_004.label_size = 20
    frame_004.shrink = True

    # Node Remove Named Attribute.002
    remove_named_attribute_002 = objectsoncurve_1.nodes.new("GeometryNodeRemoveAttribute")
    remove_named_attribute_002.name = "Remove Named Attribute.002"
    # Pattern Mode
    remove_named_attribute_002.inputs[1].default_value = 'Exact'
    # Name
    remove_named_attribute_002.inputs[2].default_value = "instance_size"

    # Node Frame.005
    frame_005 = objectsoncurve_1.nodes.new("NodeFrame")
    frame_005.label = "little cleanup"
    frame_005.name = "Frame.005"
    frame_005.label_size = 20
    frame_005.shrink = True

    # Node Named Attribute.004
    named_attribute_004 = objectsoncurve_1.nodes.new("GeometryNodeInputNamedAttribute")
    named_attribute_004.name = "Named Attribute.004"
    named_attribute_004.data_type = 'INT'
    # Name
    named_attribute_004.inputs[0].default_value = "instance_pos"

    # Node For Each Geometry Element Input.003
    for_each_geometry_element_input_003 = objectsoncurve_1.nodes.new("GeometryNodeForeachGeometryElementInput")
    for_each_geometry_element_input_003.name = "For Each Geometry Element Input.003"
    # Node For Each Geometry Element Output.003
    for_each_geometry_element_output_003 = objectsoncurve_1.nodes.new("GeometryNodeForeachGeometryElementOutput")
    for_each_geometry_element_output_003.name = "For Each Geometry Element Output.003"
    for_each_geometry_element_output_003.active_generation_index = 0
    for_each_geometry_element_output_003.active_input_index = 0
    for_each_geometry_element_output_003.active_main_index = 0
    for_each_geometry_element_output_003.domain = 'POINT'
    for_each_geometry_element_output_003.generation_items.clear()
    for_each_geometry_element_output_003.generation_items.new('GEOMETRY', "Geometry")
    for_each_geometry_element_output_003.generation_items[0].domain = 'POINT'
    for_each_geometry_element_output_003.input_items.clear()
    for_each_geometry_element_output_003.input_items.new('INT', "instance_pos")
    for_each_geometry_element_output_003.inspection_index = 0
    for_each_geometry_element_output_003.main_items.clear()

    # Node Compare.003
    compare_003 = objectsoncurve_1.nodes.new("FunctionNodeCompare")
    compare_003.name = "Compare.003"
    compare_003.hide = True
    compare_003.data_type = 'INT'
    compare_003.mode = 'ELEMENT'
    compare_003.operation = 'NOT_EQUAL'

    # Node For Each Geometry Element Input.004
    for_each_geometry_element_input_004 = objectsoncurve_1.nodes.new("GeometryNodeForeachGeometryElementInput")
    for_each_geometry_element_input_004.name = "For Each Geometry Element Input.004"
    # Node For Each Geometry Element Output.004
    for_each_geometry_element_output_004 = objectsoncurve_1.nodes.new("GeometryNodeForeachGeometryElementOutput")
    for_each_geometry_element_output_004.name = "For Each Geometry Element Output.004"
    for_each_geometry_element_output_004.active_generation_index = 0
    for_each_geometry_element_output_004.active_input_index = 0
    for_each_geometry_element_output_004.active_main_index = 0
    for_each_geometry_element_output_004.domain = 'POINT'
    for_each_geometry_element_output_004.generation_items.clear()
    for_each_geometry_element_output_004.generation_items.new('GEOMETRY', "Points")
    for_each_geometry_element_output_004.generation_items[0].domain = 'POINT'
    for_each_geometry_element_output_004.input_items.clear()
    for_each_geometry_element_output_004.inspection_index = 0
    for_each_geometry_element_output_004.main_items.clear()

    # Node Delete Geometry.002
    delete_geometry_002 = objectsoncurve_1.nodes.new("GeometryNodeDeleteGeometry")
    delete_geometry_002.name = "Delete Geometry.002"
    delete_geometry_002.hide = True
    delete_geometry_002.domain = 'POINT'
    delete_geometry_002.mode = 'ALL'

    # Node Domain Size.001
    domain_size_001 = objectsoncurve_1.nodes.new("GeometryNodeAttributeDomainSize")
    domain_size_001.name = "Domain Size.001"
    domain_size_001.hide = True
    domain_size_001.component = 'POINTCLOUD'

    # Node Compare.004
    compare_004 = objectsoncurve_1.nodes.new("FunctionNodeCompare")
    compare_004.name = "Compare.004"
    compare_004.hide = True
    compare_004.data_type = 'INT'
    compare_004.mode = 'ELEMENT'
    compare_004.operation = 'GREATER_THAN'
    # B_INT
    compare_004.inputs[3].default_value = 0

    # Node Delete Geometry.003
    delete_geometry_003 = objectsoncurve_1.nodes.new("GeometryNodeDeleteGeometry")
    delete_geometry_003.name = "Delete Geometry.003"
    delete_geometry_003.hide = True
    delete_geometry_003.domain = 'POINT'
    delete_geometry_003.mode = 'ALL'

    # Node Join Geometry
    join_geometry = objectsoncurve_1.nodes.new("GeometryNodeJoinGeometry")
    join_geometry.name = "Join Geometry"

    # Node Points.001
    points_001 = objectsoncurve_1.nodes.new("GeometryNodePoints")
    points_001.name = "Points.001"
    points_001.hide = True
    # Position
    points_001.inputs[1].default_value = (0.0, 0.0, 0.0)
    # Radius
    points_001.inputs[2].default_value = 0.10000000149011612

    # Node Attribute Statistic.002
    attribute_statistic_002 = objectsoncurve_1.nodes.new("GeometryNodeAttributeStatistic")
    attribute_statistic_002.name = "Attribute Statistic.002"
    attribute_statistic_002.hide = True
    attribute_statistic_002.data_type = 'FLOAT'
    attribute_statistic_002.domain = 'POINT'
    # Selection
    attribute_statistic_002.inputs[1].default_value = True

    # Node Named Attribute.005
    named_attribute_005 = objectsoncurve_1.nodes.new("GeometryNodeInputNamedAttribute")
    named_attribute_005.name = "Named Attribute.005"
    named_attribute_005.data_type = 'FLOAT'
    # Name
    named_attribute_005.inputs[0].default_value = "instance_size"

    # Node Math.013
    math_013 = objectsoncurve_1.nodes.new("ShaderNodeMath")
    math_013.name = "Math.013"
    math_013.hide = True
    math_013.operation = 'ADD'
    math_013.use_clamp = False
    # Value_001
    math_013.inputs[1].default_value = 1.0

    # Node Accumulate Field
    accumulate_field = objectsoncurve_1.nodes.new("GeometryNodeAccumulateField")
    accumulate_field.name = "Accumulate Field"
    accumulate_field.data_type = 'FLOAT'
    accumulate_field.domain = 'POINT'
    # Group Index
    accumulate_field.inputs[1].default_value = 0

    # Node Attribute Statistic.003
    attribute_statistic_003 = objectsoncurve_1.nodes.new("GeometryNodeAttributeStatistic")
    attribute_statistic_003.name = "Attribute Statistic.003"
    attribute_statistic_003.data_type = 'FLOAT'
    attribute_statistic_003.domain = 'POINT'
    # Selection
    attribute_statistic_003.inputs[1].default_value = True

    # Node Math.014
    math_014 = objectsoncurve_1.nodes.new("ShaderNodeMath")
    math_014.name = "Math.014"
    math_014.operation = 'SUBTRACT'
    math_014.use_clamp = False

    # Node Points.002
    points_002 = objectsoncurve_1.nodes.new("GeometryNodePoints")
    points_002.name = "Points.002"
    points_002.hide = True
    # Position
    points_002.inputs[1].default_value = (0.0, 0.0, 0.0)
    # Radius
    points_002.inputs[2].default_value = 0.10000000149011612

    # Node Math.015
    math_015 = objectsoncurve_1.nodes.new("ShaderNodeMath")
    math_015.name = "Math.015"
    math_015.operation = 'DIVIDE'
    math_015.use_clamp = False

    # Node Curve Length.001
    curve_length_001 = objectsoncurve_1.nodes.new("GeometryNodeCurveLength")
    curve_length_001.name = "Curve Length.001"

    # Node Join Geometry.002
    join_geometry_002 = objectsoncurve_1.nodes.new("GeometryNodeJoinGeometry")
    join_geometry_002.name = "Join Geometry.002"

    # Node Frame.006
    frame_006 = objectsoncurve_1.nodes.new("NodeFrame")
    frame_006.label = "generate trailing points for the remaining curve length"
    frame_006.name = "Frame.006"
    frame_006.label_size = 20
    frame_006.shrink = True

    # Node Frame.007
    frame_007 = objectsoncurve_1.nodes.new("NodeFrame")
    frame_007.label = "generate leading points (up to max point with custom position)"
    frame_007.name = "Frame.007"
    frame_007.label_size = 20
    frame_007.shrink = True

    # Node Frame.008
    frame_008 = objectsoncurve_1.nodes.new("NodeFrame")
    frame_008.label = "generate leading points with custom size defined"
    frame_008.name = "Frame.008"
    frame_008.label_size = 20
    frame_008.shrink = True

    # Node Named Attribute.006
    named_attribute_006 = objectsoncurve_1.nodes.new("GeometryNodeInputNamedAttribute")
    named_attribute_006.name = "Named Attribute.006"
    named_attribute_006.data_type = 'INT'
    # Name
    named_attribute_006.inputs[0].default_value = "instance_ref"

    # Node Frame.009
    frame_009 = objectsoncurve_1.nodes.new("NodeFrame")
    frame_009.label = "generate sample points"
    frame_009.name = "Frame.009"
    frame_009.label_size = 20
    frame_009.shrink = True

    # Node Reroute.005
    reroute_005 = objectsoncurve_1.nodes.new("NodeReroute")
    reroute_005.name = "Reroute.005"
    reroute_005.socket_idname = "NodeSocketGeometry"
    # Node Reroute.004
    reroute_004 = objectsoncurve_1.nodes.new("NodeReroute")
    reroute_004.name = "Reroute.004"
    reroute_004.socket_idname = "NodeSocketFloat"
    # Node Group Input.003
    group_input_003 = objectsoncurve_1.nodes.new("NodeGroupInput")
    group_input_003.name = "Group Input.003"
    group_input_003.outputs[0].hide = True
    group_input_003.outputs[1].hide = True
    group_input_003.outputs[3].hide = True
    group_input_003.outputs[4].hide = True

    # Node Reroute.003
    reroute_003 = objectsoncurve_1.nodes.new("NodeReroute")
    reroute_003.name = "Reroute.003"
    reroute_003.socket_idname = "NodeSocketGeometry"
    # Node Named Attribute.007
    named_attribute_007 = objectsoncurve_1.nodes.new("GeometryNodeInputNamedAttribute")
    named_attribute_007.name = "Named Attribute.007"
    named_attribute_007.data_type = 'QUATERNION'
    # Name
    named_attribute_007.inputs[0].default_value = "instance_rotation"

    # Node Rotate Instances
    rotate_instances = objectsoncurve_1.nodes.new("GeometryNodeRotateInstances")
    rotate_instances.name = "Rotate Instances"
    # Selection
    rotate_instances.inputs[1].default_value = True
    # Pivot Point
    rotate_instances.inputs[3].default_value = (0.0, 0.0, 0.0)
    # Local Space
    rotate_instances.inputs[4].default_value = True

    # Node Named Attribute.008
    named_attribute_008 = objectsoncurve_1.nodes.new("GeometryNodeInputNamedAttribute")
    named_attribute_008.name = "Named Attribute.008"
    named_attribute_008.data_type = 'FLOAT_VECTOR'
    # Name
    named_attribute_008.inputs[0].default_value = "instance_translation"

    # Node Translate Instances
    translate_instances = objectsoncurve_1.nodes.new("GeometryNodeTranslateInstances")
    translate_instances.name = "Translate Instances"
    # Selection
    translate_instances.inputs[1].default_value = True
    # Local Space
    translate_instances.inputs[3].default_value = True

    # Node Remove Named Attribute.003
    remove_named_attribute_003 = objectsoncurve_1.nodes.new("GeometryNodeRemoveAttribute")
    remove_named_attribute_003.name = "Remove Named Attribute.003"
    # Pattern Mode
    remove_named_attribute_003.inputs[1].default_value = 'Exact'
    # Name
    remove_named_attribute_003.inputs[2].default_value = "instance_pos"

    # Node Frame.010
    frame_010 = objectsoncurve_1.nodes.new("NodeFrame")
    frame_010.label = "filter segments with custom position"
    frame_010.name = "Frame.010"
    frame_010.label_size = 20
    frame_010.shrink = True

    # Node For Each Geometry Element Input.005
    for_each_geometry_element_input_005 = objectsoncurve_1.nodes.new("GeometryNodeForeachGeometryElementInput")
    for_each_geometry_element_input_005.name = "For Each Geometry Element Input.005"
    # Node For Each Geometry Element Output.005
    for_each_geometry_element_output_005 = objectsoncurve_1.nodes.new("GeometryNodeForeachGeometryElementOutput")
    for_each_geometry_element_output_005.name = "For Each Geometry Element Output.005"
    for_each_geometry_element_output_005.active_generation_index = 0
    for_each_geometry_element_output_005.active_input_index = 0
    for_each_geometry_element_output_005.active_main_index = 0
    for_each_geometry_element_output_005.domain = 'POINT'
    for_each_geometry_element_output_005.generation_items.clear()
    for_each_geometry_element_output_005.generation_items.new('GEOMETRY', "Geometry")
    for_each_geometry_element_output_005.generation_items[0].domain = 'POINT'
    for_each_geometry_element_output_005.input_items.clear()
    for_each_geometry_element_output_005.input_items.new('INT', "instance_pos")
    for_each_geometry_element_output_005.inspection_index = 0
    for_each_geometry_element_output_005.main_items.clear()

    # Node Compare.005
    compare_005 = objectsoncurve_1.nodes.new("FunctionNodeCompare")
    compare_005.name = "Compare.005"
    compare_005.hide = True
    compare_005.data_type = 'INT'
    compare_005.mode = 'ELEMENT'
    compare_005.operation = 'NOT_EQUAL'
    # B_INT
    compare_005.inputs[3].default_value = -1

    # Node Delete Geometry.004
    delete_geometry_004 = objectsoncurve_1.nodes.new("GeometryNodeDeleteGeometry")
    delete_geometry_004.name = "Delete Geometry.004"
    delete_geometry_004.hide = True
    delete_geometry_004.domain = 'POINT'
    delete_geometry_004.mode = 'ALL'

    # Node Frame.011
    frame_011 = objectsoncurve_1.nodes.new("NodeFrame")
    frame_011.label = "filter repeating (pos == -1)"
    frame_011.name = "Frame.011"
    frame_011.label_size = 20
    frame_011.shrink = True

    # Node Frame
    frame = objectsoncurve_1.nodes.new("NodeFrame")
    frame.label = "delete repeating if other segment has position defined"
    frame.name = "Frame"
    frame.label_size = 20
    frame.shrink = True

    # Node Group Input.004
    group_input_004 = objectsoncurve_1.nodes.new("NodeGroupInput")
    group_input_004.name = "Group Input.004"
    group_input_004.outputs[1].hide = True
    group_input_004.outputs[2].hide = True
    group_input_004.outputs[3].hide = True
    group_input_004.outputs[4].hide = True

    # Node For Each Geometry Element Input.001
    for_each_geometry_element_input_001 = objectsoncurve_1.nodes.new("GeometryNodeForeachGeometryElementInput")
    for_each_geometry_element_input_001.name = "For Each Geometry Element Input.001"
    # Node For Each Geometry Element Output.001
    for_each_geometry_element_output_001 = objectsoncurve_1.nodes.new("GeometryNodeForeachGeometryElementOutput")
    for_each_geometry_element_output_001.name = "For Each Geometry Element Output.001"
    for_each_geometry_element_output_001.active_generation_index = 0
    for_each_geometry_element_output_001.active_input_index = 0
    for_each_geometry_element_output_001.active_main_index = 0
    for_each_geometry_element_output_001.domain = 'POINT'
    for_each_geometry_element_output_001.generation_items.clear()
    for_each_geometry_element_output_001.generation_items.new('GEOMETRY', "Geometry")
    for_each_geometry_element_output_001.generation_items[0].domain = 'POINT'
    for_each_geometry_element_output_001.input_items.clear()
    for_each_geometry_element_output_001.inspection_index = 0
    for_each_geometry_element_output_001.main_items.clear()

    # Node For Each Geometry Element Input.006
    for_each_geometry_element_input_006 = objectsoncurve_1.nodes.new("GeometryNodeForeachGeometryElementInput")
    for_each_geometry_element_input_006.name = "For Each Geometry Element Input.006"
    # Node For Each Geometry Element Output.006
    for_each_geometry_element_output_006 = objectsoncurve_1.nodes.new("GeometryNodeForeachGeometryElementOutput")
    for_each_geometry_element_output_006.name = "For Each Geometry Element Output.006"
    for_each_geometry_element_output_006.active_generation_index = 0
    for_each_geometry_element_output_006.active_input_index = 0
    for_each_geometry_element_output_006.active_main_index = 0
    for_each_geometry_element_output_006.domain = 'POINT'
    for_each_geometry_element_output_006.generation_items.clear()
    for_each_geometry_element_output_006.generation_items.new('GEOMETRY', "Geometry")
    for_each_geometry_element_output_006.generation_items[0].domain = 'POINT'
    for_each_geometry_element_output_006.input_items.clear()
    for_each_geometry_element_output_006.input_items.new('INT', "instance_pos")
    for_each_geometry_element_output_006.inspection_index = 0
    for_each_geometry_element_output_006.main_items.clear()

    # Node Compare.006
    compare_006 = objectsoncurve_1.nodes.new("FunctionNodeCompare")
    compare_006.name = "Compare.006"
    compare_006.hide = True
    compare_006.data_type = 'INT'
    compare_006.mode = 'ELEMENT'
    compare_006.operation = 'NOT_EQUAL'
    # B_INT
    compare_006.inputs[3].default_value = -1

    # Node Delete Geometry.005
    delete_geometry_005 = objectsoncurve_1.nodes.new("GeometryNodeDeleteGeometry")
    delete_geometry_005.name = "Delete Geometry.005"
    delete_geometry_005.hide = True
    delete_geometry_005.domain = 'POINT'
    delete_geometry_005.mode = 'ALL'

    # Node Frame.003
    frame_003 = objectsoncurve_1.nodes.new("NodeFrame")
    frame_003.label = "filter only repeating (pos == -1)"
    frame_003.name = "Frame.003"
    frame_003.label_size = 20
    frame_003.shrink = True

    # Node Named Attribute.009
    named_attribute_009 = objectsoncurve_1.nodes.new("GeometryNodeInputNamedAttribute")
    named_attribute_009.name = "Named Attribute.009"
    named_attribute_009.data_type = 'INT'
    # Name
    named_attribute_009.inputs[0].default_value = "instance_pos"

    # Node Group Input.005
    group_input_005 = objectsoncurve_1.nodes.new("NodeGroupInput")
    group_input_005.name = "Group Input.005"
    group_input_005.outputs[1].hide = True
    group_input_005.outputs[2].hide = True
    group_input_005.outputs[3].hide = True
    group_input_005.outputs[4].hide = True

    # Node For Each Geometry Element Input.007
    for_each_geometry_element_input_007 = objectsoncurve_1.nodes.new("GeometryNodeForeachGeometryElementInput")
    for_each_geometry_element_input_007.name = "For Each Geometry Element Input.007"
    # Node For Each Geometry Element Output.007
    for_each_geometry_element_output_007 = objectsoncurve_1.nodes.new("GeometryNodeForeachGeometryElementOutput")
    for_each_geometry_element_output_007.name = "For Each Geometry Element Output.007"
    for_each_geometry_element_output_007.active_generation_index = 1
    for_each_geometry_element_output_007.active_input_index = 1
    for_each_geometry_element_output_007.active_main_index = 0
    for_each_geometry_element_output_007.domain = 'POINT'
    for_each_geometry_element_output_007.generation_items.clear()
    for_each_geometry_element_output_007.generation_items.new('GEOMETRY', "Geometry")
    for_each_geometry_element_output_007.generation_items[0].domain = 'POINT'
    for_each_geometry_element_output_007.generation_items.new('FLOAT', "instance_size")
    for_each_geometry_element_output_007.generation_items[1].domain = 'POINT'
    for_each_geometry_element_output_007.input_items.clear()
    for_each_geometry_element_output_007.input_items.new('INT', "instance_pos")
    for_each_geometry_element_output_007.input_items.new('FLOAT', "instance_size")
    for_each_geometry_element_output_007.inspection_index = 0
    for_each_geometry_element_output_007.main_items.clear()

    # Node Compare.007
    compare_007 = objectsoncurve_1.nodes.new("FunctionNodeCompare")
    compare_007.name = "Compare.007"
    compare_007.hide = True
    compare_007.data_type = 'INT'
    compare_007.mode = 'ELEMENT'
    compare_007.operation = 'NOT_EQUAL'
    # B_INT
    compare_007.inputs[3].default_value = -1

    # Node Delete Geometry.006
    delete_geometry_006 = objectsoncurve_1.nodes.new("GeometryNodeDeleteGeometry")
    delete_geometry_006.name = "Delete Geometry.006"
    delete_geometry_006.hide = True
    delete_geometry_006.domain = 'POINT'
    delete_geometry_006.mode = 'ALL'

    # Node Named Attribute.010
    named_attribute_010 = objectsoncurve_1.nodes.new("GeometryNodeInputNamedAttribute")
    named_attribute_010.name = "Named Attribute.010"
    named_attribute_010.data_type = 'INT'
    # Name
    named_attribute_010.inputs[0].default_value = "instance_pos"

    # Node Attribute Statistic
    attribute_statistic = objectsoncurve_1.nodes.new("GeometryNodeAttributeStatistic")
    attribute_statistic.name = "Attribute Statistic"
    attribute_statistic.data_type = 'FLOAT'
    attribute_statistic.domain = 'POINT'
    # Selection
    attribute_statistic.inputs[1].default_value = True

    # Node Frame.012
    frame_012 = objectsoncurve_1.nodes.new("NodeFrame")
    frame_012.label = "get max size of all repeating segments"
    frame_012.name = "Frame.012"
    frame_012.label_size = 20
    frame_012.shrink = True

    # Node Reroute.006
    reroute_006 = objectsoncurve_1.nodes.new("NodeReroute")
    reroute_006.name = "Reroute.006"
    reroute_006.socket_idname = "NodeSocketFloat"
    # Node Reroute.008
    reroute_008 = objectsoncurve_1.nodes.new("NodeReroute")
    reroute_008.name = "Reroute.008"
    reroute_008.socket_idname = "NodeSocketFloat"
    # Node Store Named Attribute.003
    store_named_attribute_003 = objectsoncurve_1.nodes.new("GeometryNodeStoreNamedAttribute")
    store_named_attribute_003.name = "Store Named Attribute.003"
    store_named_attribute_003.data_type = 'FLOAT'
    store_named_attribute_003.domain = 'POINT'
    # Selection
    store_named_attribute_003.inputs[1].default_value = True
    # Name
    store_named_attribute_003.inputs[2].default_value = "sample_offset"

    # Node Float to Integer
    float_to_integer = objectsoncurve_1.nodes.new("FunctionNodeFloatToInt")
    float_to_integer.name = "Float to Integer"
    float_to_integer.rounding_mode = 'TRUNCATE'

    # Node Math.001
    math_001 = objectsoncurve_1.nodes.new("ShaderNodeMath")
    math_001.name = "Math.001"
    math_001.hide = True
    math_001.operation = 'MULTIPLY'
    math_001.use_clamp = False

    # Node For Each Geometry Element Input.002
    for_each_geometry_element_input_002 = objectsoncurve_1.nodes.new("GeometryNodeForeachGeometryElementInput")
    for_each_geometry_element_input_002.name = "For Each Geometry Element Input.002"
    # Node For Each Geometry Element Output.002
    for_each_geometry_element_output_002 = objectsoncurve_1.nodes.new("GeometryNodeForeachGeometryElementOutput")
    for_each_geometry_element_output_002.name = "For Each Geometry Element Output.002"
    for_each_geometry_element_output_002.active_generation_index = 0
    for_each_geometry_element_output_002.active_input_index = 0
    for_each_geometry_element_output_002.active_main_index = 0
    for_each_geometry_element_output_002.domain = 'POINT'
    for_each_geometry_element_output_002.generation_items.clear()
    for_each_geometry_element_output_002.generation_items.new('GEOMETRY', "Geometry")
    for_each_geometry_element_output_002.generation_items[0].domain = 'POINT'
    for_each_geometry_element_output_002.input_items.clear()
    for_each_geometry_element_output_002.inspection_index = 0
    for_each_geometry_element_output_002.main_items.clear()

    # Node Store Named Attribute.004
    store_named_attribute_004 = objectsoncurve_1.nodes.new("GeometryNodeStoreNamedAttribute")
    store_named_attribute_004.name = "Store Named Attribute.004"
    store_named_attribute_004.data_type = 'FLOAT'
    store_named_attribute_004.domain = 'POINT'
    # Selection
    store_named_attribute_004.inputs[1].default_value = True
    # Name
    store_named_attribute_004.inputs[2].default_value = "sample_offset"

    # Node Math.005
    math_005 = objectsoncurve_1.nodes.new("ShaderNodeMath")
    math_005.name = "Math.005"
    math_005.hide = True
    math_005.operation = 'MULTIPLY'
    math_005.use_clamp = False

    # Node For Each Geometry Element Input.008
    for_each_geometry_element_input_008 = objectsoncurve_1.nodes.new("GeometryNodeForeachGeometryElementInput")
    for_each_geometry_element_input_008.name = "For Each Geometry Element Input.008"
    # Node For Each Geometry Element Output.008
    for_each_geometry_element_output_008 = objectsoncurve_1.nodes.new("GeometryNodeForeachGeometryElementOutput")
    for_each_geometry_element_output_008.name = "For Each Geometry Element Output.008"
    for_each_geometry_element_output_008.active_generation_index = 0
    for_each_geometry_element_output_008.active_input_index = 0
    for_each_geometry_element_output_008.active_main_index = 0
    for_each_geometry_element_output_008.domain = 'POINT'
    for_each_geometry_element_output_008.generation_items.clear()
    for_each_geometry_element_output_008.generation_items.new('GEOMETRY', "Geometry")
    for_each_geometry_element_output_008.generation_items[0].domain = 'POINT'
    for_each_geometry_element_output_008.input_items.clear()
    for_each_geometry_element_output_008.inspection_index = 0
    for_each_geometry_element_output_008.main_items.clear()

    # Node Named Attribute.001
    named_attribute_001 = objectsoncurve_1.nodes.new("GeometryNodeInputNamedAttribute")
    named_attribute_001.name = "Named Attribute.001"
    named_attribute_001.data_type = 'FLOAT'
    # Name
    named_attribute_001.inputs[0].default_value = "sample_offset"

    # Node Math.009
    math_009 = objectsoncurve_1.nodes.new("ShaderNodeMath")
    math_009.name = "Math.009"
    math_009.hide = True
    math_009.operation = 'SUBTRACT'
    math_009.use_clamp = False

    # Node Math.011
    math_011 = objectsoncurve_1.nodes.new("ShaderNodeMath")
    math_011.name = "Math.011"
    math_011.hide = True
    math_011.operation = 'SUBTRACT'
    math_011.use_clamp = False

    # Node Reroute.009
    reroute_009 = objectsoncurve_1.nodes.new("NodeReroute")
    reroute_009.name = "Reroute.009"
    reroute_009.socket_idname = "NodeSocketFloat"
    # Node Reroute.010
    reroute_010 = objectsoncurve_1.nodes.new("NodeReroute")
    reroute_010.name = "Reroute.010"
    reroute_010.socket_idname = "NodeSocketFloat"
    # Node Reroute.011
    reroute_011 = objectsoncurve_1.nodes.new("NodeReroute")
    reroute_011.name = "Reroute.011"
    reroute_011.socket_idname = "NodeSocketFloat"
    # Node Math.012
    math_012 = objectsoncurve_1.nodes.new("ShaderNodeMath")
    math_012.name = "Math.012"
    math_012.hide = True
    math_012.operation = 'ADD'
    math_012.use_clamp = False

    # Node Named Attribute.002
    named_attribute_002 = objectsoncurve_1.nodes.new("GeometryNodeInputNamedAttribute")
    named_attribute_002.name = "Named Attribute.002"
    named_attribute_002.data_type = 'FLOAT'
    # Name
    named_attribute_002.inputs[0].default_value = "instance_offset"

    # Node Frame.013
    frame_013 = objectsoncurve_1.nodes.new("NodeFrame")
    frame_013.label = "compensate so that all repeating segments are in the same place"
    frame_013.name = "Frame.013"
    frame_013.label_size = 20
    frame_013.shrink = True

    # Node Frame.014
    frame_014 = objectsoncurve_1.nodes.new("NodeFrame")
    frame_014.label = "compensate so that all repeating segments are int he same place"
    frame_014.name = "Frame.014"
    frame_014.label_size = 20
    frame_014.shrink = True

    # Node Reroute.012
    reroute_012 = objectsoncurve_1.nodes.new("NodeReroute")
    reroute_012.name = "Reroute.012"
    reroute_012.socket_idname = "NodeSocketGeometry"
    # Node Frame.015
    frame_015 = objectsoncurve_1.nodes.new("NodeFrame")
    frame_015.label = "instantiate and apply custom transform"
    frame_015.name = "Frame.015"
    frame_015.label_size = 20
    frame_015.shrink = True

    # Node Frame.016
    frame_016 = objectsoncurve_1.nodes.new("NodeFrame")
    frame_016.label = "sample curve based on generated points"
    frame_016.name = "Frame.016"
    frame_016.label_size = 20
    frame_016.shrink = True

    # Process zone input For Each Geometry Element Input
    for_each_geometry_element_input.pair_with_output(for_each_geometry_element_output)
    # Selection
    for_each_geometry_element_input.inputs[1].default_value = True


    # Process zone input For Each Geometry Element Input.003
    for_each_geometry_element_input_003.pair_with_output(for_each_geometry_element_output_003)
    # Selection
    for_each_geometry_element_input_003.inputs[1].default_value = True


    # Process zone input For Each Geometry Element Input.004
    for_each_geometry_element_input_004.pair_with_output(for_each_geometry_element_output_004)
    # Selection
    for_each_geometry_element_input_004.inputs[1].default_value = True


    # Process zone input For Each Geometry Element Input.005
    for_each_geometry_element_input_005.pair_with_output(for_each_geometry_element_output_005)
    # Selection
    for_each_geometry_element_input_005.inputs[1].default_value = True


    # Process zone input For Each Geometry Element Input.001
    for_each_geometry_element_input_001.pair_with_output(for_each_geometry_element_output_001)
    # Selection
    for_each_geometry_element_input_001.inputs[1].default_value = True


    # Process zone input For Each Geometry Element Input.006
    for_each_geometry_element_input_006.pair_with_output(for_each_geometry_element_output_006)
    # Selection
    for_each_geometry_element_input_006.inputs[1].default_value = True


    # Process zone input For Each Geometry Element Input.007
    for_each_geometry_element_input_007.pair_with_output(for_each_geometry_element_output_007)
    # Selection
    for_each_geometry_element_input_007.inputs[1].default_value = True


    # Process zone input For Each Geometry Element Input.002
    for_each_geometry_element_input_002.pair_with_output(for_each_geometry_element_output_002)
    # Selection
    for_each_geometry_element_input_002.inputs[1].default_value = True


    # Process zone input For Each Geometry Element Input.008
    for_each_geometry_element_input_008.pair_with_output(for_each_geometry_element_output_008)
    # Selection
    for_each_geometry_element_input_008.inputs[1].default_value = True



    # Set parents
    objectsoncurve_1.nodes["Instance on Points"].parent = objectsoncurve_1.nodes["Frame.015"]
    objectsoncurve_1.nodes["Domain Size"].parent = objectsoncurve_1.nodes["Frame.001"]
    objectsoncurve_1.nodes["Index"].parent = objectsoncurve_1.nodes["Frame.001"]
    objectsoncurve_1.nodes["Named Attribute"].parent = objectsoncurve_1.nodes["Frame.001"]
    objectsoncurve_1.nodes["Store Named Attribute"].parent = objectsoncurve_1.nodes["Frame.001"]
    objectsoncurve_1.nodes["Vector Math"].parent = objectsoncurve_1.nodes["Frame.001"]
    objectsoncurve_1.nodes["Capture Attribute.001"].parent = objectsoncurve_1.nodes["Frame.001"]
    objectsoncurve_1.nodes["Combine XYZ"].parent = objectsoncurve_1.nodes["Frame.001"]
    objectsoncurve_1.nodes["Vector Math.001"].parent = objectsoncurve_1.nodes["Frame.001"]
    objectsoncurve_1.nodes["Math.002"].parent = objectsoncurve_1.nodes["Frame.001"]
    objectsoncurve_1.nodes["Math.003"].parent = objectsoncurve_1.nodes["Frame.001"]
    objectsoncurve_1.nodes["Math.004"].parent = objectsoncurve_1.nodes["Frame.001"]
    objectsoncurve_1.nodes["Math.006"].parent = objectsoncurve_1.nodes["Frame.001"]
    objectsoncurve_1.nodes["Math.007"].parent = objectsoncurve_1.nodes["Frame.001"]
    objectsoncurve_1.nodes["Math.008"].parent = objectsoncurve_1.nodes["Frame.001"]
    objectsoncurve_1.nodes["Math.010"].parent = objectsoncurve_1.nodes["Frame.001"]
    objectsoncurve_1.nodes["Instances to Points"].parent = objectsoncurve_1.nodes["Frame.002"]
    objectsoncurve_1.nodes["Capture Attribute.003"].parent = objectsoncurve_1.nodes["Frame.002"]
    objectsoncurve_1.nodes["Instance Transform"].parent = objectsoncurve_1.nodes["Frame.002"]
    objectsoncurve_1.nodes["Separate Transform"].parent = objectsoncurve_1.nodes["Frame.002"]
    objectsoncurve_1.nodes["Store Named Attribute.001"].parent = objectsoncurve_1.nodes["Frame.002"]
    objectsoncurve_1.nodes["Store Named Attribute.002"].parent = objectsoncurve_1.nodes["Frame.002"]
    objectsoncurve_1.nodes["Group Output.001"].parent = objectsoncurve_1.nodes["Frame.002"]
    objectsoncurve_1.nodes["Points to Vertices"].parent = objectsoncurve_1.nodes["Frame.002"]
    objectsoncurve_1.nodes["Collection Info"].parent = objectsoncurve_1.nodes["Frame.015"]
    objectsoncurve_1.nodes["Remove Named Attribute.001"].parent = objectsoncurve_1.nodes["Frame.005"]
    objectsoncurve_1.nodes["Group Input.002"].parent = objectsoncurve_1.nodes["Frame.007"]
    objectsoncurve_1.nodes["For Each Geometry Element Input"].parent = objectsoncurve_1.nodes["Frame.016"]
    objectsoncurve_1.nodes["For Each Geometry Element Output"].parent = objectsoncurve_1.nodes["Frame.016"]
    objectsoncurve_1.nodes["Sample Curve.002"].parent = objectsoncurve_1.nodes["Frame.004"]
    objectsoncurve_1.nodes["Set Position"].parent = objectsoncurve_1.nodes["Frame.016"]
    objectsoncurve_1.nodes["Capture Attribute"].parent = objectsoncurve_1.nodes["Frame.016"]
    objectsoncurve_1.nodes["Align Rotation to Vector.004"].parent = objectsoncurve_1.nodes["Frame.016"]
    objectsoncurve_1.nodes["Mix.003"].parent = objectsoncurve_1.nodes["Frame.004"]
    objectsoncurve_1.nodes["Sample Curve.003"].parent = objectsoncurve_1.nodes["Frame.004"]
    objectsoncurve_1.nodes["Compare"].parent = objectsoncurve_1.nodes["Frame.004"]
    objectsoncurve_1.nodes["Switch"].parent = objectsoncurve_1.nodes["Frame.004"]
    objectsoncurve_1.nodes["Curve of Point"].parent = objectsoncurve_1.nodes["Frame.016"]
    objectsoncurve_1.nodes["Index.001"].parent = objectsoncurve_1.nodes["Frame.016"]
    objectsoncurve_1.nodes["Frame.004"].parent = objectsoncurve_1.nodes["Frame.016"]
    objectsoncurve_1.nodes["Remove Named Attribute.002"].parent = objectsoncurve_1.nodes["Frame.005"]
    objectsoncurve_1.nodes["Named Attribute.004"].parent = objectsoncurve_1.nodes["Frame.007"]
    objectsoncurve_1.nodes["For Each Geometry Element Input.003"].parent = objectsoncurve_1.nodes["Frame.010"]
    objectsoncurve_1.nodes["For Each Geometry Element Output.003"].parent = objectsoncurve_1.nodes["Frame.010"]
    objectsoncurve_1.nodes["Compare.003"].parent = objectsoncurve_1.nodes["Frame.010"]
    objectsoncurve_1.nodes["For Each Geometry Element Input.004"].parent = objectsoncurve_1.nodes["Frame.007"]
    objectsoncurve_1.nodes["For Each Geometry Element Output.004"].parent = objectsoncurve_1.nodes["Frame.007"]
    objectsoncurve_1.nodes["Delete Geometry.002"].parent = objectsoncurve_1.nodes["Frame.010"]
    objectsoncurve_1.nodes["Domain Size.001"].parent = objectsoncurve_1.nodes["Frame"]
    objectsoncurve_1.nodes["Compare.004"].parent = objectsoncurve_1.nodes["Frame"]
    objectsoncurve_1.nodes["Delete Geometry.003"].parent = objectsoncurve_1.nodes["Frame"]
    objectsoncurve_1.nodes["Join Geometry"].parent = objectsoncurve_1.nodes["Frame"]
    objectsoncurve_1.nodes["Points.001"].parent = objectsoncurve_1.nodes["Frame.008"]
    objectsoncurve_1.nodes["Attribute Statistic.002"].parent = objectsoncurve_1.nodes["Frame.008"]
    objectsoncurve_1.nodes["Named Attribute.005"].parent = objectsoncurve_1.nodes["Frame.009"]
    objectsoncurve_1.nodes["Math.013"].parent = objectsoncurve_1.nodes["Frame.008"]
    objectsoncurve_1.nodes["Accumulate Field"].parent = objectsoncurve_1.nodes["Frame.009"]
    objectsoncurve_1.nodes["Attribute Statistic.003"].parent = objectsoncurve_1.nodes["Frame.006"]
    objectsoncurve_1.nodes["Math.014"].parent = objectsoncurve_1.nodes["Frame.006"]
    objectsoncurve_1.nodes["Points.002"].parent = objectsoncurve_1.nodes["Frame.006"]
    objectsoncurve_1.nodes["Math.015"].parent = objectsoncurve_1.nodes["Frame.006"]
    objectsoncurve_1.nodes["Curve Length.001"].parent = objectsoncurve_1.nodes["Frame.006"]
    objectsoncurve_1.nodes["Join Geometry.002"].parent = objectsoncurve_1.nodes["Frame.009"]
    objectsoncurve_1.nodes["Frame.006"].parent = objectsoncurve_1.nodes["Frame.009"]
    objectsoncurve_1.nodes["Frame.007"].parent = objectsoncurve_1.nodes["Frame.009"]
    objectsoncurve_1.nodes["Frame.008"].parent = objectsoncurve_1.nodes["Frame.007"]
    objectsoncurve_1.nodes["Named Attribute.006"].parent = objectsoncurve_1.nodes["Frame.015"]
    objectsoncurve_1.nodes["Reroute.005"].parent = objectsoncurve_1.nodes["Frame.007"]
    objectsoncurve_1.nodes["Reroute.004"].parent = objectsoncurve_1.nodes["Frame.009"]
    objectsoncurve_1.nodes["Group Input.003"].parent = objectsoncurve_1.nodes["Frame.015"]
    objectsoncurve_1.nodes["Reroute.003"].parent = objectsoncurve_1.nodes["Frame.001"]
    objectsoncurve_1.nodes["Named Attribute.007"].parent = objectsoncurve_1.nodes["Frame.015"]
    objectsoncurve_1.nodes["Rotate Instances"].parent = objectsoncurve_1.nodes["Frame.015"]
    objectsoncurve_1.nodes["Named Attribute.008"].parent = objectsoncurve_1.nodes["Frame.015"]
    objectsoncurve_1.nodes["Translate Instances"].parent = objectsoncurve_1.nodes["Frame.015"]
    objectsoncurve_1.nodes["Remove Named Attribute.003"].parent = objectsoncurve_1.nodes["Frame.005"]
    objectsoncurve_1.nodes["Frame.010"].parent = objectsoncurve_1.nodes["Frame.007"]
    objectsoncurve_1.nodes["For Each Geometry Element Input.005"].parent = objectsoncurve_1.nodes["Frame.011"]
    objectsoncurve_1.nodes["For Each Geometry Element Output.005"].parent = objectsoncurve_1.nodes["Frame.011"]
    objectsoncurve_1.nodes["Compare.005"].parent = objectsoncurve_1.nodes["Frame.011"]
    objectsoncurve_1.nodes["Delete Geometry.004"].parent = objectsoncurve_1.nodes["Frame.011"]
    objectsoncurve_1.nodes["Frame.011"].parent = objectsoncurve_1.nodes["Frame.007"]
    objectsoncurve_1.nodes["Frame"].parent = objectsoncurve_1.nodes["Frame.007"]
    objectsoncurve_1.nodes["Group Input.004"].parent = objectsoncurve_1.nodes["Frame.003"]
    objectsoncurve_1.nodes["For Each Geometry Element Input.001"].parent = objectsoncurve_1.nodes["Frame.003"]
    objectsoncurve_1.nodes["For Each Geometry Element Output.001"].parent = objectsoncurve_1.nodes["Frame.009"]
    objectsoncurve_1.nodes["For Each Geometry Element Input.006"].parent = objectsoncurve_1.nodes["Frame.003"]
    objectsoncurve_1.nodes["For Each Geometry Element Output.006"].parent = objectsoncurve_1.nodes["Frame.003"]
    objectsoncurve_1.nodes["Compare.006"].parent = objectsoncurve_1.nodes["Frame.003"]
    objectsoncurve_1.nodes["Delete Geometry.005"].parent = objectsoncurve_1.nodes["Frame.003"]
    objectsoncurve_1.nodes["Frame.003"].parent = objectsoncurve_1.nodes["Frame.009"]
    objectsoncurve_1.nodes["Named Attribute.009"].parent = objectsoncurve_1.nodes["Frame.003"]
    objectsoncurve_1.nodes["Group Input.005"].parent = objectsoncurve_1.nodes["Frame.012"]
    objectsoncurve_1.nodes["For Each Geometry Element Input.007"].parent = objectsoncurve_1.nodes["Frame.012"]
    objectsoncurve_1.nodes["For Each Geometry Element Output.007"].parent = objectsoncurve_1.nodes["Frame.012"]
    objectsoncurve_1.nodes["Compare.007"].parent = objectsoncurve_1.nodes["Frame.012"]
    objectsoncurve_1.nodes["Delete Geometry.006"].parent = objectsoncurve_1.nodes["Frame.012"]
    objectsoncurve_1.nodes["Named Attribute.010"].parent = objectsoncurve_1.nodes["Frame.012"]
    objectsoncurve_1.nodes["Attribute Statistic"].parent = objectsoncurve_1.nodes["Frame.012"]
    objectsoncurve_1.nodes["Frame.012"].parent = objectsoncurve_1.nodes["Frame.009"]
    objectsoncurve_1.nodes["Reroute.006"].parent = objectsoncurve_1.nodes["Frame.009"]
    objectsoncurve_1.nodes["Reroute.008"].parent = objectsoncurve_1.nodes["Frame.009"]
    objectsoncurve_1.nodes["Store Named Attribute.003"].parent = objectsoncurve_1.nodes["Frame.013"]
    objectsoncurve_1.nodes["Float to Integer"].parent = objectsoncurve_1.nodes["Frame.006"]
    objectsoncurve_1.nodes["Math.001"].parent = objectsoncurve_1.nodes["Frame.013"]
    objectsoncurve_1.nodes["For Each Geometry Element Input.002"].parent = objectsoncurve_1.nodes["Frame.013"]
    objectsoncurve_1.nodes["For Each Geometry Element Output.002"].parent = objectsoncurve_1.nodes["Frame.013"]
    objectsoncurve_1.nodes["Store Named Attribute.004"].parent = objectsoncurve_1.nodes["Frame.014"]
    objectsoncurve_1.nodes["Math.005"].parent = objectsoncurve_1.nodes["Frame.014"]
    objectsoncurve_1.nodes["For Each Geometry Element Input.008"].parent = objectsoncurve_1.nodes["Frame.014"]
    objectsoncurve_1.nodes["For Each Geometry Element Output.008"].parent = objectsoncurve_1.nodes["Frame.014"]
    objectsoncurve_1.nodes["Named Attribute.001"].parent = objectsoncurve_1.nodes["Frame.016"]
    objectsoncurve_1.nodes["Math.009"].parent = objectsoncurve_1.nodes["Frame.016"]
    objectsoncurve_1.nodes["Math.011"].parent = objectsoncurve_1.nodes["Frame.016"]
    objectsoncurve_1.nodes["Reroute.009"].parent = objectsoncurve_1.nodes["Frame.009"]
    objectsoncurve_1.nodes["Reroute.010"].parent = objectsoncurve_1.nodes["Frame.009"]
    objectsoncurve_1.nodes["Reroute.011"].parent = objectsoncurve_1.nodes["Frame.009"]
    objectsoncurve_1.nodes["Math.012"].parent = objectsoncurve_1.nodes["Frame.016"]
    objectsoncurve_1.nodes["Named Attribute.002"].parent = objectsoncurve_1.nodes["Frame.016"]
    objectsoncurve_1.nodes["Frame.013"].parent = objectsoncurve_1.nodes["Frame.007"]
    objectsoncurve_1.nodes["Frame.014"].parent = objectsoncurve_1.nodes["Frame.009"]
    objectsoncurve_1.nodes["Reroute.012"].parent = objectsoncurve_1.nodes["Frame.009"]

    # Set locations
    objectsoncurve_1.nodes["Group Input"].location = (-6237.38037109375, 40.209598541259766)
    objectsoncurve_1.nodes["Group Output"].location = (5444.33935546875, 16.9924373626709)
    objectsoncurve_1.nodes["Instance on Points"].location = (414.703369140625, -236.20596313476562)
    objectsoncurve_1.nodes["Object Info"].location = (-5937.38037109375, -179.7904052734375)
    objectsoncurve_1.nodes["Realize Instances"].location = (3522.0, 20.0)
    objectsoncurve_1.nodes["Domain Size"].location = (495.7928466796875, -276.0)
    objectsoncurve_1.nodes["Index"].location = (33.7926025390625, -516.0)
    objectsoncurve_1.nodes["Named Attribute"].location = (1093.7926025390625, -36.0)
    objectsoncurve_1.nodes["Store Named Attribute"].location = (2355.79248046875, -376.0)
    objectsoncurve_1.nodes["Vector Math"].location = (2095.79248046875, -336.0)
    objectsoncurve_1.nodes["Capture Attribute.001"].location = (755.7926025390625, -416.0)
    objectsoncurve_1.nodes["Combine XYZ"].location = (1855.7926025390625, -436.0)
    objectsoncurve_1.nodes["Vector Math.001"].location = (1795.7926025390625, -276.0)
    objectsoncurve_1.nodes["Math.002"].location = (935.7926025390625, -256.0)
    objectsoncurve_1.nodes["Math.003"].location = (1075.7926025390625, -376.0)
    objectsoncurve_1.nodes["Math.004"].location = (655.7926025390625, -176.0)
    objectsoncurve_1.nodes["Math.006"].location = (1175.7926025390625, -256.0)
    objectsoncurve_1.nodes["Math.007"].location = (1495.7926025390625, -216.0)
    objectsoncurve_1.nodes["Math.008"].location = (815.7926025390625, -176.0)
    objectsoncurve_1.nodes["Math.010"].location = (1495.7926025390625, -396.0)
    objectsoncurve_1.nodes["Transform Geometry.001"].location = (4401.99951171875, 20.0)
    objectsoncurve_1.nodes["Instances to Points"].location = (752.0, -56.0)
    objectsoncurve_1.nodes["Capture Attribute.003"].location = (532.0, -96.0)
    objectsoncurve_1.nodes["Instance Transform"].location = (30.0, -196.0)
    objectsoncurve_1.nodes["Separate Transform"].location = (250.0, -136.0)
    objectsoncurve_1.nodes["Store Named Attribute.001"].location = (1131.99951171875, -36.0)
    objectsoncurve_1.nodes["Store Named Attribute.002"].location = (1291.99951171875, -56.0)
    objectsoncurve_1.nodes["Reroute"].location = (3182.0, -40.0)
    objectsoncurve_1.nodes["Frame.001"].location = (1506.2073974609375, 656.0)
    objectsoncurve_1.nodes["Reroute.001"].location = (3520.0, -160.0)
    objectsoncurve_1.nodes["Group Output.001"].location = (1531.99951171875, -96.0)
    objectsoncurve_1.nodes["Points to Vertices"].location = (932.0, -56.0)
    objectsoncurve_1.nodes["Frame.002"].location = (3130.0, -324.0)
    objectsoncurve_1.nodes["Reroute.002"].location = (-5573.60400390625, 108.64167785644531)
    objectsoncurve_1.nodes["Self Object"].location = (-6217.38037109375, -739.7904052734375)
    objectsoncurve_1.nodes["Object Info.001"].location = (-5957.38037109375, -599.7904052734375)
    objectsoncurve_1.nodes["Invert Matrix"].location = (-5737.38037109375, -519.7904052734375)
    objectsoncurve_1.nodes["Multiply Matrices"].location = (-5577.38037109375, -339.7903747558594)
    objectsoncurve_1.nodes["Collection Info"].location = (220.37774658203125, -89.4853515625)
    objectsoncurve_1.nodes["Remove Named Attribute.001"].location = (277.99951171875, -37.0)
    objectsoncurve_1.nodes["Group Input.002"].location = (29.96875, -238.0489501953125)
    objectsoncurve_1.nodes["For Each Geometry Element Input"].location = (151.61474609375, -234.8463134765625)
    objectsoncurve_1.nodes["For Each Geometry Element Output"].location = (2256.483642578125, -243.72247314453125)
    objectsoncurve_1.nodes["Sample Curve.002"].location = (30.4840087890625, -209.72247314453125)
    objectsoncurve_1.nodes["Set Position"].location = (2056.483642578125, -363.72247314453125)
    objectsoncurve_1.nodes["Capture Attribute"].location = (1838.04833984375, -303.6749267578125)
    objectsoncurve_1.nodes["Align Rotation to Vector.004"].location = (1596.4837646484375, -343.72247314453125)
    objectsoncurve_1.nodes["Mix.003"].location = (730.4837036132812, -69.72247314453125)
    objectsoncurve_1.nodes["Sample Curve.003"].location = (30.4840087890625, -49.72247314453125)
    objectsoncurve_1.nodes["Reroute.007"].location = (-1776.2236328125, 48.43208312988281)
    objectsoncurve_1.nodes["Group Input.001"].location = (3160.0, 40.0)
    objectsoncurve_1.nodes["Compare"].location = (250.4840087890625, -69.72247314453125)
    objectsoncurve_1.nodes["Switch"].location = (450.48370361328125, -69.72247314453125)
    objectsoncurve_1.nodes["Curve of Point"].location = (281.4786376953125, -39.25848388671875)
    objectsoncurve_1.nodes["Index.001"].location = (76.97412109375, -36.43408203125)
    objectsoncurve_1.nodes["Frame.004"].location = (626.0, -174.0)
    objectsoncurve_1.nodes["Remove Named Attribute.002"].location = (477.99951171875, -37.0)
    objectsoncurve_1.nodes["Frame.005"].location = (4584.0, 57.0)
    objectsoncurve_1.nodes["Named Attribute.004"].location = (147.2158203125, -438.10089111328125)
    objectsoncurve_1.nodes["For Each Geometry Element Input.003"].location = (29.73095703125, -55.8319091796875)
    objectsoncurve_1.nodes["For Each Geometry Element Output.003"].location = (549.73095703125, -55.8319091796875)
    objectsoncurve_1.nodes["Compare.003"].location = (229.73095703125, -135.8319091796875)
    objectsoncurve_1.nodes["For Each Geometry Element Input.004"].location = (1201.12646484375, -703.7723388671875)
    objectsoncurve_1.nodes["For Each Geometry Element Output.004"].location = (3410.17529296875, -489.41827392578125)
    objectsoncurve_1.nodes["Delete Geometry.002"].location = (389.73095703125, -135.8319091796875)
    objectsoncurve_1.nodes["Domain Size.001"].location = (30.37353515625, -40.4171142578125)
    objectsoncurve_1.nodes["Compare.004"].location = (166.1103515625, -70.746337890625)
    objectsoncurve_1.nodes["Delete Geometry.003"].location = (303.96240234375, -120.857177734375)
    objectsoncurve_1.nodes["Join Geometry"].location = (468.58251953125, -68.783447265625)
    objectsoncurve_1.nodes["Points.001"].location = (429.70361328125, -70.36135864257812)
    objectsoncurve_1.nodes["Attribute Statistic.002"].location = (29.703125, -70.36135864257812)
    objectsoncurve_1.nodes["Named Attribute.005"].location = (120.4814453125, -35.533935546875)
    objectsoncurve_1.nodes["Math.013"].location = (249.703125, -70.36135864257812)
    objectsoncurve_1.nodes["Accumulate Field"].location = (6769.1669921875, -492.980224609375)
    objectsoncurve_1.nodes["Attribute Statistic.003"].location = (30.10009765625, -35.5794677734375)
    objectsoncurve_1.nodes["Math.014"].location = (434.92333984375, -214.844970703125)
    objectsoncurve_1.nodes["Points.002"].location = (1057.41943359375, -300.38690185546875)
    objectsoncurve_1.nodes["Math.015"].location = (666.673828125, -214.844970703125)
    objectsoncurve_1.nodes["Curve Length.001"].location = (211.345703125, -292.0599365234375)
    objectsoncurve_1.nodes["Join Geometry.002"].location = (6789.2265625, -1152.2952880859375)
    objectsoncurve_1.nodes["Frame.006"].location = (3720.0, -543.0)
    objectsoncurve_1.nodes["Frame.007"].location = (30.0, -497.0)
    objectsoncurve_1.nodes["Frame.008"].location = (521.0, -683.0)
    objectsoncurve_1.nodes["Named Attribute.006"].location = (132.7034912109375, -496.20599365234375)
    objectsoncurve_1.nodes["Frame.009"].location = (-9125.0, 1745.0)
    objectsoncurve_1.nodes["Reroute.005"].location = (306.873046875, -269.25177001953125)
    objectsoncurve_1.nodes["Reroute.004"].location = (5886.2197265625, -81.0380859375)
    objectsoncurve_1.nodes["Group Input.003"].location = (29.921051025390625, -38.5343017578125)
    objectsoncurve_1.nodes["Reroute.003"].location = (35.0, -368.0328369140625)
    objectsoncurve_1.nodes["Named Attribute.007"].location = (732.7034912109375, -36.20599365234375)
    objectsoncurve_1.nodes["Rotate Instances"].location = (954.7037353515625, -176.20596313476562)
    objectsoncurve_1.nodes["Named Attribute.008"].location = (492.70343017578125, -36.20599365234375)
    objectsoncurve_1.nodes["Translate Instances"].location = (714.703369140625, -216.20596313476562)
    objectsoncurve_1.nodes["Remove Named Attribute.003"].location = (30.10009765625, -36.058631896972656)
    objectsoncurve_1.nodes["Frame.010"].location = (1214.0, -36.0)
    objectsoncurve_1.nodes["For Each Geometry Element Input.005"].location = (30.4814453125, -56.286376953125)
    objectsoncurve_1.nodes["For Each Geometry Element Output.005"].location = (511.91162109375, -80.564208984375)
    objectsoncurve_1.nodes["Compare.005"].location = (206.04052734375, -185.7508544921875)
    objectsoncurve_1.nodes["Delete Geometry.004"].location = (362.416015625, -211.97509765625)
    objectsoncurve_1.nodes["Frame.011"].location = (1212.0, -346.0)
    objectsoncurve_1.nodes["Frame"].location = (2772.0, -490.0)
    objectsoncurve_1.nodes["Group Input.004"].location = (36.1865234375, -35.6134033203125)
    objectsoncurve_1.nodes["For Each Geometry Element Input.001"].location = (30.26806640625, -292.8172607421875)
    objectsoncurve_1.nodes["For Each Geometry Element Output.001"].location = (6614.5546875, -855.3697509765625)
    objectsoncurve_1.nodes["For Each Geometry Element Input.006"].location = (238.072998046875, -161.13720703125)
    objectsoncurve_1.nodes["For Each Geometry Element Output.006"].location = (692.049072265625, -168.9962158203125)
    objectsoncurve_1.nodes["Compare.006"].location = (407.189697265625, -301.3382568359375)
    objectsoncurve_1.nodes["Delete Geometry.005"].location = (553.86669921875, -291.5555419921875)
    objectsoncurve_1.nodes["Frame.003"].location = (4991.0, -542.0)
    objectsoncurve_1.nodes["Named Attribute.009"].location = (40.41650390625, -124.2047119140625)
    objectsoncurve_1.nodes["Group Input.005"].location = (30.0791015625, -117.2999267578125)
    objectsoncurve_1.nodes["For Each Geometry Element Input.007"].location = (311.7060546875, -90.9970703125)
    objectsoncurve_1.nodes["For Each Geometry Element Output.007"].location = (745.34765625, -104.7103271484375)
    objectsoncurve_1.nodes["Compare.007"].location = (486.7119140625, -208.1060791015625)
    objectsoncurve_1.nodes["Delete Geometry.006"].location = (626.1328125, -192.131591796875)
    objectsoncurve_1.nodes["Named Attribute.010"].location = (30.8466796875, -199.942138671875)
    objectsoncurve_1.nodes["Attribute Statistic"].location = (960.1728515625, -35.5771484375)
    objectsoncurve_1.nodes["Frame.012"].location = (530.0, -91.0)
    objectsoncurve_1.nodes["Reroute.006"].location = (3456.61181640625, -68.3565673828125)
    objectsoncurve_1.nodes["Reroute.008"].location = (722.525390625, -66.6748046875)
    objectsoncurve_1.nodes["Store Named Attribute.003"].location = (448.1953125, -57.38104248046875)
    objectsoncurve_1.nodes["Float to Integer"].location = (863.35693359375, -246.335205078125)
    objectsoncurve_1.nodes["Math.001"].location = (254.67822265625, -58.76971435546875)
    objectsoncurve_1.nodes["For Each Geometry Element Input.002"].location = (29.9052734375, -55.98388671875)
    objectsoncurve_1.nodes["For Each Geometry Element Output.002"].location = (634.61572265625, -70.6719970703125)
    objectsoncurve_1.nodes["Store Named Attribute.004"].location = (365.76904296875, -51.91455078125)
    objectsoncurve_1.nodes["Math.005"].location = (205.098876953125, -67.72674560546875)
    objectsoncurve_1.nodes["For Each Geometry Element Input.008"].location = (29.893798828125, -56.4998779296875)
    objectsoncurve_1.nodes["For Each Geometry Element Output.008"].location = (539.678955078125, -64.9637451171875)
    objectsoncurve_1.nodes["Named Attribute.001"].location = (34.297119140625, -643.23876953125)
    objectsoncurve_1.nodes["Math.009"].location = (411.2718505859375, -259.0443115234375)
    objectsoncurve_1.nodes["Math.011"].location = (427.7877197265625, -396.66680908203125)
    objectsoncurve_1.nodes["Reroute.009"].location = (2015.71875, -316.0291748046875)
    objectsoncurve_1.nodes["Reroute.010"].location = (4259.634765625, -303.4029541015625)
    objectsoncurve_1.nodes["Reroute.011"].location = (5946.5546875, -319.856201171875)
    objectsoncurve_1.nodes["Math.012"].location = (239.6387939453125, -629.9187622070312)
    objectsoncurve_1.nodes["Named Attribute.002"].location = (29.85546875, -502.82818603515625)
    objectsoncurve_1.nodes["Frame.013"].location = (1916.0, -420.0)
    objectsoncurve_1.nodes["Frame.014"].location = (5875.0, -656.0)
    objectsoncurve_1.nodes["Reroute.012"].location = (2634.59130859375, -859.9940185546875)
    objectsoncurve_1.nodes["Frame.015"].location = (347.0, 656.0)
    objectsoncurve_1.nodes["Frame.016"].location = (-2096.0, 765.0)

    # Set dimensions
    objectsoncurve_1.nodes["Group Input"].width  = 140.0
    objectsoncurve_1.nodes["Group Input"].height = 100.0

    objectsoncurve_1.nodes["Group Output"].width  = 140.0
    objectsoncurve_1.nodes["Group Output"].height = 100.0

    objectsoncurve_1.nodes["Instance on Points"].width  = 140.0
    objectsoncurve_1.nodes["Instance on Points"].height = 100.0

    objectsoncurve_1.nodes["Object Info"].width  = 140.0
    objectsoncurve_1.nodes["Object Info"].height = 100.0

    objectsoncurve_1.nodes["Realize Instances"].width  = 140.0
    objectsoncurve_1.nodes["Realize Instances"].height = 100.0

    objectsoncurve_1.nodes["Domain Size"].width  = 140.0
    objectsoncurve_1.nodes["Domain Size"].height = 100.0

    objectsoncurve_1.nodes["Index"].width  = 140.0
    objectsoncurve_1.nodes["Index"].height = 100.0

    objectsoncurve_1.nodes["Named Attribute"].width  = 140.0
    objectsoncurve_1.nodes["Named Attribute"].height = 100.0

    objectsoncurve_1.nodes["Store Named Attribute"].width  = 140.0
    objectsoncurve_1.nodes["Store Named Attribute"].height = 100.0

    objectsoncurve_1.nodes["Vector Math"].width  = 140.0
    objectsoncurve_1.nodes["Vector Math"].height = 100.0

    objectsoncurve_1.nodes["Capture Attribute.001"].width  = 140.0
    objectsoncurve_1.nodes["Capture Attribute.001"].height = 100.0

    objectsoncurve_1.nodes["Combine XYZ"].width  = 140.0
    objectsoncurve_1.nodes["Combine XYZ"].height = 100.0

    objectsoncurve_1.nodes["Vector Math.001"].width  = 140.0
    objectsoncurve_1.nodes["Vector Math.001"].height = 100.0

    objectsoncurve_1.nodes["Math.002"].width  = 195.587158203125
    objectsoncurve_1.nodes["Math.002"].height = 100.0

    objectsoncurve_1.nodes["Math.003"].width  = 228.7255859375
    objectsoncurve_1.nodes["Math.003"].height = 100.0

    objectsoncurve_1.nodes["Math.004"].width  = 140.0
    objectsoncurve_1.nodes["Math.004"].height = 100.0

    objectsoncurve_1.nodes["Math.006"].width  = 140.0
    objectsoncurve_1.nodes["Math.006"].height = 100.0

    objectsoncurve_1.nodes["Math.007"].width  = 159.776123046875
    objectsoncurve_1.nodes["Math.007"].height = 100.0

    objectsoncurve_1.nodes["Math.008"].width  = 140.0
    objectsoncurve_1.nodes["Math.008"].height = 100.0

    objectsoncurve_1.nodes["Math.010"].width  = 228.7255859375
    objectsoncurve_1.nodes["Math.010"].height = 100.0

    objectsoncurve_1.nodes["Transform Geometry.001"].width  = 140.0
    objectsoncurve_1.nodes["Transform Geometry.001"].height = 100.0

    objectsoncurve_1.nodes["Instances to Points"].width  = 140.0
    objectsoncurve_1.nodes["Instances to Points"].height = 100.0

    objectsoncurve_1.nodes["Capture Attribute.003"].width  = 140.0
    objectsoncurve_1.nodes["Capture Attribute.003"].height = 100.0

    objectsoncurve_1.nodes["Instance Transform"].width  = 140.0
    objectsoncurve_1.nodes["Instance Transform"].height = 100.0

    objectsoncurve_1.nodes["Separate Transform"].width  = 140.0
    objectsoncurve_1.nodes["Separate Transform"].height = 100.0

    objectsoncurve_1.nodes["Store Named Attribute.001"].width  = 140.0
    objectsoncurve_1.nodes["Store Named Attribute.001"].height = 100.0

    objectsoncurve_1.nodes["Store Named Attribute.002"].width  = 140.0
    objectsoncurve_1.nodes["Store Named Attribute.002"].height = 100.0

    objectsoncurve_1.nodes["Reroute"].width  = 10.0
    objectsoncurve_1.nodes["Reroute"].height = 100.0

    objectsoncurve_1.nodes["Frame.001"].width  = 2525.79248046875
    objectsoncurve_1.nodes["Frame.001"].height = 596.0

    objectsoncurve_1.nodes["Reroute.001"].width  = 10.0
    objectsoncurve_1.nodes["Reroute.001"].height = 100.0

    objectsoncurve_1.nodes["Group Output.001"].width  = 140.0
    objectsoncurve_1.nodes["Group Output.001"].height = 100.0

    objectsoncurve_1.nodes["Points to Vertices"].width  = 140.0
    objectsoncurve_1.nodes["Points to Vertices"].height = 100.0

    objectsoncurve_1.nodes["Frame.002"].width  = 1702.0
    objectsoncurve_1.nodes["Frame.002"].height = 285.0

    objectsoncurve_1.nodes["Reroute.002"].width  = 10.0
    objectsoncurve_1.nodes["Reroute.002"].height = 100.0

    objectsoncurve_1.nodes["Self Object"].width  = 140.0
    objectsoncurve_1.nodes["Self Object"].height = 100.0

    objectsoncurve_1.nodes["Object Info.001"].width  = 140.0
    objectsoncurve_1.nodes["Object Info.001"].height = 100.0

    objectsoncurve_1.nodes["Invert Matrix"].width  = 140.0
    objectsoncurve_1.nodes["Invert Matrix"].height = 100.0

    objectsoncurve_1.nodes["Multiply Matrices"].width  = 140.0
    objectsoncurve_1.nodes["Multiply Matrices"].height = 100.0

    objectsoncurve_1.nodes["Collection Info"].width  = 140.0
    objectsoncurve_1.nodes["Collection Info"].height = 100.0

    objectsoncurve_1.nodes["Remove Named Attribute.001"].width  = 170.0
    objectsoncurve_1.nodes["Remove Named Attribute.001"].height = 100.0

    objectsoncurve_1.nodes["Group Input.002"].width  = 140.0
    objectsoncurve_1.nodes["Group Input.002"].height = 100.0

    objectsoncurve_1.nodes["For Each Geometry Element Input"].width  = 140.0
    objectsoncurve_1.nodes["For Each Geometry Element Input"].height = 100.0

    objectsoncurve_1.nodes["For Each Geometry Element Output"].width  = 140.0
    objectsoncurve_1.nodes["For Each Geometry Element Output"].height = 100.0

    objectsoncurve_1.nodes["Sample Curve.002"].width  = 140.0
    objectsoncurve_1.nodes["Sample Curve.002"].height = 100.0

    objectsoncurve_1.nodes["Set Position"].width  = 140.0
    objectsoncurve_1.nodes["Set Position"].height = 100.0

    objectsoncurve_1.nodes["Capture Attribute"].width  = 140.0
    objectsoncurve_1.nodes["Capture Attribute"].height = 100.0

    objectsoncurve_1.nodes["Align Rotation to Vector.004"].width  = 171.867431640625
    objectsoncurve_1.nodes["Align Rotation to Vector.004"].height = 100.0

    objectsoncurve_1.nodes["Mix.003"].width  = 140.0
    objectsoncurve_1.nodes["Mix.003"].height = 100.0

    objectsoncurve_1.nodes["Sample Curve.003"].width  = 140.0
    objectsoncurve_1.nodes["Sample Curve.003"].height = 100.0

    objectsoncurve_1.nodes["Reroute.007"].width  = 10.0
    objectsoncurve_1.nodes["Reroute.007"].height = 100.0

    objectsoncurve_1.nodes["Group Input.001"].width  = 140.0
    objectsoncurve_1.nodes["Group Input.001"].height = 100.0

    objectsoncurve_1.nodes["Compare"].width  = 140.0
    objectsoncurve_1.nodes["Compare"].height = 100.0

    objectsoncurve_1.nodes["Switch"].width  = 140.0
    objectsoncurve_1.nodes["Switch"].height = 100.0

    objectsoncurve_1.nodes["Curve of Point"].width  = 140.0
    objectsoncurve_1.nodes["Curve of Point"].height = 100.0

    objectsoncurve_1.nodes["Index.001"].width  = 140.0
    objectsoncurve_1.nodes["Index.001"].height = 100.0

    objectsoncurve_1.nodes["Frame.004"].width  = 900.0
    objectsoncurve_1.nodes["Frame.004"].height = 297.0

    objectsoncurve_1.nodes["Remove Named Attribute.002"].width  = 170.0
    objectsoncurve_1.nodes["Remove Named Attribute.002"].height = 100.0

    objectsoncurve_1.nodes["Frame.005"].width  = 678.0
    objectsoncurve_1.nodes["Frame.005"].height = 159.0

    objectsoncurve_1.nodes["Named Attribute.004"].width  = 140.0
    objectsoncurve_1.nodes["Named Attribute.004"].height = 100.0

    objectsoncurve_1.nodes["For Each Geometry Element Input.003"].width  = 140.0
    objectsoncurve_1.nodes["For Each Geometry Element Input.003"].height = 100.0

    objectsoncurve_1.nodes["For Each Geometry Element Output.003"].width  = 140.0
    objectsoncurve_1.nodes["For Each Geometry Element Output.003"].height = 100.0

    objectsoncurve_1.nodes["Compare.003"].width  = 100.0
    objectsoncurve_1.nodes["Compare.003"].height = 100.0

    objectsoncurve_1.nodes["For Each Geometry Element Input.004"].width  = 140.0
    objectsoncurve_1.nodes["For Each Geometry Element Input.004"].height = 100.0

    objectsoncurve_1.nodes["For Each Geometry Element Output.004"].width  = 140.0
    objectsoncurve_1.nodes["For Each Geometry Element Output.004"].height = 100.0

    objectsoncurve_1.nodes["Delete Geometry.002"].width  = 100.0
    objectsoncurve_1.nodes["Delete Geometry.002"].height = 100.0

    objectsoncurve_1.nodes["Domain Size.001"].width  = 100.0
    objectsoncurve_1.nodes["Domain Size.001"].height = 100.0

    objectsoncurve_1.nodes["Compare.004"].width  = 100.0
    objectsoncurve_1.nodes["Compare.004"].height = 100.0

    objectsoncurve_1.nodes["Delete Geometry.003"].width  = 100.0
    objectsoncurve_1.nodes["Delete Geometry.003"].height = 100.0

    objectsoncurve_1.nodes["Join Geometry"].width  = 100.0
    objectsoncurve_1.nodes["Join Geometry"].height = 100.0

    objectsoncurve_1.nodes["Points.001"].width  = 140.0
    objectsoncurve_1.nodes["Points.001"].height = 100.0

    objectsoncurve_1.nodes["Attribute Statistic.002"].width  = 140.0
    objectsoncurve_1.nodes["Attribute Statistic.002"].height = 100.0

    objectsoncurve_1.nodes["Named Attribute.005"].width  = 140.0
    objectsoncurve_1.nodes["Named Attribute.005"].height = 100.0

    objectsoncurve_1.nodes["Math.013"].width  = 140.0
    objectsoncurve_1.nodes["Math.013"].height = 100.0

    objectsoncurve_1.nodes["Accumulate Field"].width  = 140.0
    objectsoncurve_1.nodes["Accumulate Field"].height = 100.0

    objectsoncurve_1.nodes["Attribute Statistic.003"].width  = 140.0
    objectsoncurve_1.nodes["Attribute Statistic.003"].height = 100.0

    objectsoncurve_1.nodes["Math.014"].width  = 140.0
    objectsoncurve_1.nodes["Math.014"].height = 100.0

    objectsoncurve_1.nodes["Points.002"].width  = 140.0
    objectsoncurve_1.nodes["Points.002"].height = 100.0

    objectsoncurve_1.nodes["Math.015"].width  = 140.0
    objectsoncurve_1.nodes["Math.015"].height = 100.0

    objectsoncurve_1.nodes["Curve Length.001"].width  = 140.0
    objectsoncurve_1.nodes["Curve Length.001"].height = 100.0

    objectsoncurve_1.nodes["Join Geometry.002"].width  = 100.0
    objectsoncurve_1.nodes["Join Geometry.002"].height = 100.0

    objectsoncurve_1.nodes["Frame.006"].width  = 1227.0
    objectsoncurve_1.nodes["Frame.006"].height = 397.0

    objectsoncurve_1.nodes["Frame.007"].width  = 3580.0
    objectsoncurve_1.nodes["Frame.007"].height = 916.0

    objectsoncurve_1.nodes["Frame.008"].width  = 600.0
    objectsoncurve_1.nodes["Frame.008"].height = 154.0

    objectsoncurve_1.nodes["Named Attribute.006"].width  = 140.0
    objectsoncurve_1.nodes["Named Attribute.006"].height = 100.0

    objectsoncurve_1.nodes["Frame.009"].width  = 6939.0
    objectsoncurve_1.nodes["Frame.009"].height = 1443.0

    objectsoncurve_1.nodes["Reroute.005"].width  = 10.0
    objectsoncurve_1.nodes["Reroute.005"].height = 100.0

    objectsoncurve_1.nodes["Reroute.004"].width  = 10.0
    objectsoncurve_1.nodes["Reroute.004"].height = 100.0

    objectsoncurve_1.nodes["Group Input.003"].width  = 140.0
    objectsoncurve_1.nodes["Group Input.003"].height = 100.0

    objectsoncurve_1.nodes["Reroute.003"].width  = 10.0
    objectsoncurve_1.nodes["Reroute.003"].height = 100.0

    objectsoncurve_1.nodes["Named Attribute.007"].width  = 140.0
    objectsoncurve_1.nodes["Named Attribute.007"].height = 100.0

    objectsoncurve_1.nodes["Rotate Instances"].width  = 140.0
    objectsoncurve_1.nodes["Rotate Instances"].height = 100.0

    objectsoncurve_1.nodes["Named Attribute.008"].width  = 140.0
    objectsoncurve_1.nodes["Named Attribute.008"].height = 100.0

    objectsoncurve_1.nodes["Translate Instances"].width  = 140.0
    objectsoncurve_1.nodes["Translate Instances"].height = 100.0

    objectsoncurve_1.nodes["Remove Named Attribute.003"].width  = 170.0
    objectsoncurve_1.nodes["Remove Named Attribute.003"].height = 100.0

    objectsoncurve_1.nodes["Frame.010"].width  = 720.0
    objectsoncurve_1.nodes["Frame.010"].height = 290.0

    objectsoncurve_1.nodes["For Each Geometry Element Input.005"].width  = 140.0
    objectsoncurve_1.nodes["For Each Geometry Element Input.005"].height = 100.0

    objectsoncurve_1.nodes["For Each Geometry Element Output.005"].width  = 140.0
    objectsoncurve_1.nodes["For Each Geometry Element Output.005"].height = 100.0

    objectsoncurve_1.nodes["Compare.005"].width  = 100.0
    objectsoncurve_1.nodes["Compare.005"].height = 100.0

    objectsoncurve_1.nodes["Delete Geometry.004"].width  = 100.0
    objectsoncurve_1.nodes["Delete Geometry.004"].height = 100.0

    objectsoncurve_1.nodes["Frame.011"].width  = 682.0
    objectsoncurve_1.nodes["Frame.011"].height = 290.0

    objectsoncurve_1.nodes["Frame"].width  = 599.0
    objectsoncurve_1.nodes["Frame"].height = 175.0

    objectsoncurve_1.nodes["Group Input.004"].width  = 140.0
    objectsoncurve_1.nodes["Group Input.004"].height = 100.0

    objectsoncurve_1.nodes["For Each Geometry Element Input.001"].width  = 140.0
    objectsoncurve_1.nodes["For Each Geometry Element Input.001"].height = 100.0

    objectsoncurve_1.nodes["For Each Geometry Element Output.001"].width  = 140.0
    objectsoncurve_1.nodes["For Each Geometry Element Output.001"].height = 100.0

    objectsoncurve_1.nodes["For Each Geometry Element Input.006"].width  = 140.0
    objectsoncurve_1.nodes["For Each Geometry Element Input.006"].height = 100.0

    objectsoncurve_1.nodes["For Each Geometry Element Output.006"].width  = 140.0
    objectsoncurve_1.nodes["For Each Geometry Element Output.006"].height = 100.0

    objectsoncurve_1.nodes["Compare.006"].width  = 100.0
    objectsoncurve_1.nodes["Compare.006"].height = 100.0

    objectsoncurve_1.nodes["Delete Geometry.005"].width  = 100.0
    objectsoncurve_1.nodes["Delete Geometry.005"].height = 100.0

    objectsoncurve_1.nodes["Frame.003"].width  = 862.0
    objectsoncurve_1.nodes["Frame.003"].height = 505.0

    objectsoncurve_1.nodes["Named Attribute.009"].width  = 140.0
    objectsoncurve_1.nodes["Named Attribute.009"].height = 100.0

    objectsoncurve_1.nodes["Group Input.005"].width  = 140.0
    objectsoncurve_1.nodes["Group Input.005"].height = 100.0

    objectsoncurve_1.nodes["For Each Geometry Element Input.007"].width  = 140.0
    objectsoncurve_1.nodes["For Each Geometry Element Input.007"].height = 100.0

    objectsoncurve_1.nodes["For Each Geometry Element Output.007"].width  = 140.0
    objectsoncurve_1.nodes["For Each Geometry Element Output.007"].height = 100.0

    objectsoncurve_1.nodes["Compare.007"].width  = 100.0
    objectsoncurve_1.nodes["Compare.007"].height = 100.0

    objectsoncurve_1.nodes["Delete Geometry.006"].width  = 100.0
    objectsoncurve_1.nodes["Delete Geometry.006"].height = 100.0

    objectsoncurve_1.nodes["Named Attribute.010"].width  = 140.0
    objectsoncurve_1.nodes["Named Attribute.010"].height = 100.0

    objectsoncurve_1.nodes["Attribute Statistic"].width  = 140.0
    objectsoncurve_1.nodes["Attribute Statistic"].height = 100.0

    objectsoncurve_1.nodes["Frame.012"].width  = 1130.0
    objectsoncurve_1.nodes["Frame.012"].height = 388.0

    objectsoncurve_1.nodes["Reroute.006"].width  = 10.0
    objectsoncurve_1.nodes["Reroute.006"].height = 100.0

    objectsoncurve_1.nodes["Reroute.008"].width  = 10.0
    objectsoncurve_1.nodes["Reroute.008"].height = 100.0

    objectsoncurve_1.nodes["Store Named Attribute.003"].width  = 140.0
    objectsoncurve_1.nodes["Store Named Attribute.003"].height = 100.0

    objectsoncurve_1.nodes["Float to Integer"].width  = 140.0
    objectsoncurve_1.nodes["Float to Integer"].height = 100.0

    objectsoncurve_1.nodes["Math.001"].width  = 140.0
    objectsoncurve_1.nodes["Math.001"].height = 100.0

    objectsoncurve_1.nodes["For Each Geometry Element Input.002"].width  = 140.0
    objectsoncurve_1.nodes["For Each Geometry Element Input.002"].height = 100.0

    objectsoncurve_1.nodes["For Each Geometry Element Output.002"].width  = 140.0
    objectsoncurve_1.nodes["For Each Geometry Element Output.002"].height = 100.0

    objectsoncurve_1.nodes["Store Named Attribute.004"].width  = 140.0
    objectsoncurve_1.nodes["Store Named Attribute.004"].height = 100.0

    objectsoncurve_1.nodes["Math.005"].width  = 140.0
    objectsoncurve_1.nodes["Math.005"].height = 100.0

    objectsoncurve_1.nodes["For Each Geometry Element Input.008"].width  = 140.0
    objectsoncurve_1.nodes["For Each Geometry Element Input.008"].height = 100.0

    objectsoncurve_1.nodes["For Each Geometry Element Output.008"].width  = 140.0
    objectsoncurve_1.nodes["For Each Geometry Element Output.008"].height = 100.0

    objectsoncurve_1.nodes["Named Attribute.001"].width  = 140.0
    objectsoncurve_1.nodes["Named Attribute.001"].height = 100.0

    objectsoncurve_1.nodes["Math.009"].width  = 140.0
    objectsoncurve_1.nodes["Math.009"].height = 100.0

    objectsoncurve_1.nodes["Math.011"].width  = 140.0
    objectsoncurve_1.nodes["Math.011"].height = 100.0

    objectsoncurve_1.nodes["Reroute.009"].width  = 10.0
    objectsoncurve_1.nodes["Reroute.009"].height = 100.0

    objectsoncurve_1.nodes["Reroute.010"].width  = 10.0
    objectsoncurve_1.nodes["Reroute.010"].height = 100.0

    objectsoncurve_1.nodes["Reroute.011"].width  = 10.0
    objectsoncurve_1.nodes["Reroute.011"].height = 100.0

    objectsoncurve_1.nodes["Math.012"].width  = 140.0
    objectsoncurve_1.nodes["Math.012"].height = 100.0

    objectsoncurve_1.nodes["Named Attribute.002"].width  = 140.0
    objectsoncurve_1.nodes["Named Attribute.002"].height = 100.0

    objectsoncurve_1.nodes["Frame.013"].width  = 805.0
    objectsoncurve_1.nodes["Frame.013"].height = 268.0

    objectsoncurve_1.nodes["Frame.014"].width  = 710.0
    objectsoncurve_1.nodes["Frame.014"].height = 268.0

    objectsoncurve_1.nodes["Reroute.012"].width  = 10.0
    objectsoncurve_1.nodes["Reroute.012"].height = 100.0

    objectsoncurve_1.nodes["Frame.015"].width  = 1125.0
    objectsoncurve_1.nodes["Frame.015"].height = 647.0

    objectsoncurve_1.nodes["Frame.016"].width  = 2426.0
    objectsoncurve_1.nodes["Frame.016"].height = 794.0


    # Initialize objectsoncurve_1 links

    # group_input.Curve -> object_info.Object
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Group Input"].outputs[1],
        objectsoncurve_1.nodes["Object Info"].inputs[0]
    )
    # reroute_003.Output -> domain_size.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Reroute.003"].outputs[0],
        objectsoncurve_1.nodes["Domain Size"].inputs[0]
    )
    # vector_math.Vector -> store_named_attribute.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Vector Math"].outputs[0],
        objectsoncurve_1.nodes["Store Named Attribute"].inputs[3]
    )
    # realize_instances.Geometry -> store_named_attribute.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Realize Instances"].outputs[0],
        objectsoncurve_1.nodes["Store Named Attribute"].inputs[0]
    )
    # reroute_003.Output -> capture_attribute_001.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Reroute.003"].outputs[0],
        objectsoncurve_1.nodes["Capture Attribute.001"].inputs[0]
    )
    # index.Index -> capture_attribute_001.Float
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Index"].outputs[0],
        objectsoncurve_1.nodes["Capture Attribute.001"].inputs[1]
    )
    # combine_xyz.Vector -> vector_math.Vector
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Combine XYZ"].outputs[0],
        objectsoncurve_1.nodes["Vector Math"].inputs[1]
    )
    # named_attribute.Attribute -> vector_math_001.Vector
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Named Attribute"].outputs[0],
        objectsoncurve_1.nodes["Vector Math.001"].inputs[0]
    )
    # vector_math_001.Vector -> vector_math.Vector
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Vector Math.001"].outputs[0],
        objectsoncurve_1.nodes["Vector Math"].inputs[0]
    )
    # domain_size.Instance Count -> math_004.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Domain Size"].outputs[5],
        objectsoncurve_1.nodes["Math.004"].inputs[0]
    )
    # math_002.Value -> math_006.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Math.002"].outputs[0],
        objectsoncurve_1.nodes["Math.006"].inputs[0]
    )
    # capture_attribute_001.Float -> math_002.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Capture Attribute.001"].outputs[1],
        objectsoncurve_1.nodes["Math.002"].inputs[0]
    )
    # math_008.Value -> math_007.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Math.008"].outputs[0],
        objectsoncurve_1.nodes["Math.007"].inputs[1]
    )
    # math_006.Value -> math_007.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Math.006"].outputs[0],
        objectsoncurve_1.nodes["Math.007"].inputs[0]
    )
    # math_004.Value -> math_008.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Math.004"].outputs[0],
        objectsoncurve_1.nodes["Math.008"].inputs[0]
    )
    # math_007.Value -> combine_xyz.Y
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Math.007"].outputs[0],
        objectsoncurve_1.nodes["Combine XYZ"].inputs[1]
    )
    # math_008.Value -> math_002.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Math.008"].outputs[0],
        objectsoncurve_1.nodes["Math.002"].inputs[1]
    )
    # math_008.Value -> math_003.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Math.008"].outputs[0],
        objectsoncurve_1.nodes["Math.003"].inputs[1]
    )
    # math_008.Value -> vector_math_001.Vector
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Math.008"].outputs[0],
        objectsoncurve_1.nodes["Vector Math.001"].inputs[1]
    )
    # capture_attribute_001.Float -> math_003.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Capture Attribute.001"].outputs[1],
        objectsoncurve_1.nodes["Math.003"].inputs[0]
    )
    # math_010.Value -> combine_xyz.X
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Math.010"].outputs[0],
        objectsoncurve_1.nodes["Combine XYZ"].inputs[0]
    )
    # math_003.Value -> math_010.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Math.003"].outputs[0],
        objectsoncurve_1.nodes["Math.010"].inputs[0]
    )
    # math_006.Value -> math_010.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Math.006"].outputs[0],
        objectsoncurve_1.nodes["Math.010"].inputs[1]
    )
    # reroute_001.Output -> transform_geometry_001.Transform
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Reroute.001"].outputs[0],
        objectsoncurve_1.nodes["Transform Geometry.001"].inputs[5]
    )
    # reroute.Output -> realize_instances.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Reroute"].outputs[0],
        objectsoncurve_1.nodes["Realize Instances"].inputs[0]
    )
    # store_named_attribute.Geometry -> transform_geometry_001.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Store Named Attribute"].outputs[0],
        objectsoncurve_1.nodes["Transform Geometry.001"].inputs[0]
    )
    # capture_attribute_003.Geometry -> instances_to_points.Instances
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Capture Attribute.003"].outputs[0],
        objectsoncurve_1.nodes["Instances to Points"].inputs[0]
    )
    # reroute.Output -> capture_attribute_003.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Reroute"].outputs[0],
        objectsoncurve_1.nodes["Capture Attribute.003"].inputs[0]
    )
    # instance_transform.Transform -> separate_transform.Transform
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Instance Transform"].outputs[0],
        objectsoncurve_1.nodes["Separate Transform"].inputs[0]
    )
    # separate_transform.Translation -> capture_attribute_003.Position
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Separate Transform"].outputs[0],
        objectsoncurve_1.nodes["Capture Attribute.003"].inputs[1]
    )
    # separate_transform.Rotation -> capture_attribute_003.Rotation
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Separate Transform"].outputs[1],
        objectsoncurve_1.nodes["Capture Attribute.003"].inputs[2]
    )
    # capture_attribute_003.Rotation -> store_named_attribute_002.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Capture Attribute.003"].outputs[2],
        objectsoncurve_1.nodes["Store Named Attribute.002"].inputs[3]
    )
    # capture_attribute_003.Position -> store_named_attribute_001.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Capture Attribute.003"].outputs[1],
        objectsoncurve_1.nodes["Store Named Attribute.001"].inputs[3]
    )
    # store_named_attribute_001.Geometry -> store_named_attribute_002.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Store Named Attribute.001"].outputs[0],
        objectsoncurve_1.nodes["Store Named Attribute.002"].inputs[0]
    )
    # multiply_matrices.Matrix -> reroute_001.Input
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Multiply Matrices"].outputs[0],
        objectsoncurve_1.nodes["Reroute.001"].inputs[0]
    )
    # capture_attribute_001.Geometry -> reroute.Input
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Capture Attribute.001"].outputs[0],
        objectsoncurve_1.nodes["Reroute"].inputs[0]
    )
    # points_to_vertices.Mesh -> store_named_attribute_001.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Points to Vertices"].outputs[0],
        objectsoncurve_1.nodes["Store Named Attribute.001"].inputs[0]
    )
    # store_named_attribute_002.Geometry -> group_output_001.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Store Named Attribute.002"].outputs[0],
        objectsoncurve_1.nodes["Group Output.001"].inputs[0]
    )
    # instances_to_points.Points -> points_to_vertices.Points
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Instances to Points"].outputs[0],
        objectsoncurve_1.nodes["Points to Vertices"].inputs[0]
    )
    # object_info.Geometry -> reroute_002.Input
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Object Info"].outputs[4],
        objectsoncurve_1.nodes["Reroute.002"].inputs[0]
    )
    # self_object.Self Object -> object_info_001.Object
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Self Object"].outputs[0],
        objectsoncurve_1.nodes["Object Info.001"].inputs[0]
    )
    # object_info_001.Transform -> invert_matrix.Matrix
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Object Info.001"].outputs[0],
        objectsoncurve_1.nodes["Invert Matrix"].inputs[0]
    )
    # object_info.Transform -> multiply_matrices.Matrix
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Object Info"].outputs[0],
        objectsoncurve_1.nodes["Multiply Matrices"].inputs[0]
    )
    # invert_matrix.Matrix -> multiply_matrices.Matrix
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Invert Matrix"].outputs[0],
        objectsoncurve_1.nodes["Multiply Matrices"].inputs[1]
    )
    # reroute_007.Output -> sample_curve_002.Curves
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Reroute.007"].outputs[0],
        objectsoncurve_1.nodes["Sample Curve.002"].inputs[0]
    )
    # sample_curve_002.Position -> set_position.Position
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Sample Curve.002"].outputs[1],
        objectsoncurve_1.nodes["Set Position"].inputs[2]
    )
    # set_position.Geometry -> for_each_geometry_element_output.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Set Position"].outputs[0],
        objectsoncurve_1.nodes["For Each Geometry Element Output"].inputs[1]
    )
    # for_each_geometry_element_output.Geometry -> instance_on_points.Points
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Output"].outputs[2],
        objectsoncurve_1.nodes["Instance on Points"].inputs[0]
    )
    # capture_attribute.Geometry -> set_position.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Capture Attribute"].outputs[0],
        objectsoncurve_1.nodes["Set Position"].inputs[0]
    )
    # align_rotation_to_vector_004.Rotation -> capture_attribute.Rotation
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Align Rotation to Vector.004"].outputs[0],
        objectsoncurve_1.nodes["Capture Attribute"].inputs[1]
    )
    # capture_attribute.Rotation -> for_each_geometry_element_output.Rotation
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Capture Attribute"].outputs[1],
        objectsoncurve_1.nodes["For Each Geometry Element Output"].inputs[2]
    )
    # for_each_geometry_element_output.Rotation -> instance_on_points.Rotation
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Output"].outputs[3],
        objectsoncurve_1.nodes["Instance on Points"].inputs[5]
    )
    # sample_curve_002.Tangent -> mix_003.B
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Sample Curve.002"].outputs[2],
        objectsoncurve_1.nodes["Mix.003"].inputs[5]
    )
    # mix_003.Result -> align_rotation_to_vector_004.Vector
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Mix.003"].outputs[1],
        objectsoncurve_1.nodes["Align Rotation to Vector.004"].inputs[2]
    )
    # reroute_007.Output -> sample_curve_003.Curves
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Reroute.007"].outputs[0],
        objectsoncurve_1.nodes["Sample Curve.003"].inputs[0]
    )
    # sample_curve_003.Tangent -> mix_003.A
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Sample Curve.003"].outputs[2],
        objectsoncurve_1.nodes["Mix.003"].inputs[4]
    )
    # reroute_002.Output -> reroute_007.Input
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Reroute.002"].outputs[0],
        objectsoncurve_1.nodes["Reroute.007"].inputs[0]
    )
    # group_input_001.Realize Instances -> realize_instances.Selection
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Group Input.001"].outputs[3],
        objectsoncurve_1.nodes["Realize Instances"].inputs[1]
    )
    # sample_curve_003.Value -> compare.A
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Sample Curve.003"].outputs[0],
        objectsoncurve_1.nodes["Compare"].inputs[2]
    )
    # sample_curve_002.Value -> compare.B
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Sample Curve.002"].outputs[0],
        objectsoncurve_1.nodes["Compare"].inputs[3]
    )
    # compare.Result -> switch.Switch
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Compare"].outputs[0],
        objectsoncurve_1.nodes["Switch"].inputs[0]
    )
    # switch.Output -> mix_003.Factor
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Switch"].outputs[0],
        objectsoncurve_1.nodes["Mix.003"].inputs[0]
    )
    # index_001.Index -> curve_of_point.Point Index
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Index.001"].outputs[0],
        objectsoncurve_1.nodes["Curve of Point"].inputs[0]
    )
    # curve_of_point.Curve Index -> sample_curve_003.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Curve of Point"].outputs[0],
        objectsoncurve_1.nodes["Sample Curve.003"].inputs[1]
    )
    # curve_of_point.Curve Index -> sample_curve_002.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Curve of Point"].outputs[0],
        objectsoncurve_1.nodes["Sample Curve.002"].inputs[1]
    )
    # for_each_geometry_element_input.Element -> capture_attribute.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Input"].outputs[1],
        objectsoncurve_1.nodes["Capture Attribute"].inputs[0]
    )
    # remove_named_attribute_001.Geometry -> remove_named_attribute_002.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Remove Named Attribute.001"].outputs[0],
        objectsoncurve_1.nodes["Remove Named Attribute.002"].inputs[0]
    )
    # compare_003.Result -> delete_geometry_002.Selection
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Compare.003"].outputs[0],
        objectsoncurve_1.nodes["Delete Geometry.002"].inputs[1]
    )
    # for_each_geometry_element_input_003.instance_pos -> compare_003.A
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Input.003"].outputs[2],
        objectsoncurve_1.nodes["Compare.003"].inputs[2]
    )
    # domain_size_001.Point Count -> compare_004.A
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Domain Size.001"].outputs[0],
        objectsoncurve_1.nodes["Compare.004"].inputs[2]
    )
    # points_001.Points -> for_each_geometry_element_input_004.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Points.001"].outputs[0],
        objectsoncurve_1.nodes["For Each Geometry Element Input.004"].inputs[0]
    )
    # math_014.Value -> math_015.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Math.014"].outputs[0],
        objectsoncurve_1.nodes["Math.015"].inputs[0]
    )
    # compare_004.Result -> delete_geometry_003.Selection
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Compare.004"].outputs[0],
        objectsoncurve_1.nodes["Delete Geometry.003"].inputs[1]
    )
    # named_attribute_004.Attribute -> attribute_statistic_002.Attribute
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Named Attribute.004"].outputs[0],
        objectsoncurve_1.nodes["Attribute Statistic.002"].inputs[2]
    )
    # for_each_geometry_element_input_004.Element -> delete_geometry_002.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Input.004"].outputs[1],
        objectsoncurve_1.nodes["Delete Geometry.002"].inputs[0]
    )
    # delete_geometry_003.Geometry -> join_geometry.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Delete Geometry.003"].outputs[0],
        objectsoncurve_1.nodes["Join Geometry"].inputs[0]
    )
    # attribute_statistic_003.Sum -> math_014.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Attribute Statistic.003"].outputs[2],
        objectsoncurve_1.nodes["Math.014"].inputs[1]
    )
    # curve_length_001.Length -> math_014.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Curve Length.001"].outputs[0],
        objectsoncurve_1.nodes["Math.014"].inputs[0]
    )
    # delete_geometry_002.Geometry -> for_each_geometry_element_output_003.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Delete Geometry.002"].outputs[0],
        objectsoncurve_1.nodes["For Each Geometry Element Output.003"].inputs[1]
    )
    # math_013.Value -> points_001.Count
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Math.013"].outputs[0],
        objectsoncurve_1.nodes["Points.001"].inputs[0]
    )
    # named_attribute_004.Attribute -> for_each_geometry_element_input_003.instance_pos
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Named Attribute.004"].outputs[0],
        objectsoncurve_1.nodes["For Each Geometry Element Input.003"].inputs[2]
    )
    # for_each_geometry_element_input_004.Index -> compare_003.B
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Input.004"].outputs[0],
        objectsoncurve_1.nodes["Compare.003"].inputs[3]
    )
    # join_geometry.Geometry -> for_each_geometry_element_output_004.Points
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Join Geometry"].outputs[0],
        objectsoncurve_1.nodes["For Each Geometry Element Output.004"].inputs[1]
    )
    # attribute_statistic_002.Max -> math_013.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Attribute Statistic.002"].outputs[4],
        objectsoncurve_1.nodes["Math.013"].inputs[0]
    )
    # reroute_004.Output -> accumulate_field.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Reroute.004"].outputs[0],
        objectsoncurve_1.nodes["Accumulate Field"].inputs[0]
    )
    # for_each_geometry_element_output_004.Points -> attribute_statistic_003.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Output.004"].outputs[2],
        objectsoncurve_1.nodes["Attribute Statistic.003"].inputs[0]
    )
    # reroute_006.Output -> attribute_statistic_003.Attribute
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Reroute.006"].outputs[0],
        objectsoncurve_1.nodes["Attribute Statistic.003"].inputs[2]
    )
    # reroute_005.Output -> for_each_geometry_element_input_003.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Reroute.005"].outputs[0],
        objectsoncurve_1.nodes["For Each Geometry Element Input.003"].inputs[0]
    )
    # reroute_005.Output -> attribute_statistic_002.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Reroute.005"].outputs[0],
        objectsoncurve_1.nodes["Attribute Statistic.002"].inputs[0]
    )
    # reroute_002.Output -> curve_length_001.Curve
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Reroute.002"].outputs[0],
        objectsoncurve_1.nodes["Curve Length.001"].inputs[0]
    )
    # join_geometry_002.Geometry -> for_each_geometry_element_input.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Join Geometry.002"].outputs[0],
        objectsoncurve_1.nodes["For Each Geometry Element Input"].inputs[0]
    )
    # accumulate_field.Leading -> for_each_geometry_element_input.Sample Point Tail
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Accumulate Field"].outputs[0],
        objectsoncurve_1.nodes["For Each Geometry Element Input"].inputs[2]
    )
    # accumulate_field.Trailing -> for_each_geometry_element_input.Sample Point Head
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Accumulate Field"].outputs[1],
        objectsoncurve_1.nodes["For Each Geometry Element Input"].inputs[3]
    )
    # named_attribute_006.Attribute -> instance_on_points.Instance Index
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Named Attribute.006"].outputs[0],
        objectsoncurve_1.nodes["Instance on Points"].inputs[4]
    )
    # reroute_006.Output -> reroute_004.Input
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Reroute.006"].outputs[0],
        objectsoncurve_1.nodes["Reroute.004"].inputs[0]
    )
    # group_input_003.Elements -> collection_info.Collection
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Group Input.003"].outputs[2],
        objectsoncurve_1.nodes["Collection Info"].inputs[0]
    )
    # remove_named_attribute_002.Geometry -> group_output.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Remove Named Attribute.002"].outputs[0],
        objectsoncurve_1.nodes["Group Output"].inputs[0]
    )
    # translate_instances.Instances -> rotate_instances.Instances
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Translate Instances"].outputs[0],
        objectsoncurve_1.nodes["Rotate Instances"].inputs[0]
    )
    # rotate_instances.Instances -> reroute_003.Input
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Rotate Instances"].outputs[0],
        objectsoncurve_1.nodes["Reroute.003"].inputs[0]
    )
    # instance_on_points.Instances -> translate_instances.Instances
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Instance on Points"].outputs[0],
        objectsoncurve_1.nodes["Translate Instances"].inputs[0]
    )
    # named_attribute_008.Attribute -> translate_instances.Translation
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Named Attribute.008"].outputs[0],
        objectsoncurve_1.nodes["Translate Instances"].inputs[2]
    )
    # named_attribute_007.Attribute -> rotate_instances.Rotation
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Named Attribute.007"].outputs[0],
        objectsoncurve_1.nodes["Rotate Instances"].inputs[2]
    )
    # transform_geometry_001.Geometry -> remove_named_attribute_003.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Transform Geometry.001"].outputs[0],
        objectsoncurve_1.nodes["Remove Named Attribute.003"].inputs[0]
    )
    # remove_named_attribute_003.Geometry -> remove_named_attribute_001.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Remove Named Attribute.003"].outputs[0],
        objectsoncurve_1.nodes["Remove Named Attribute.001"].inputs[0]
    )
    # collection_info.Instances -> instance_on_points.Instance
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Collection Info"].outputs[0],
        objectsoncurve_1.nodes["Instance on Points"].inputs[2]
    )
    # group_input_002.Geometry -> reroute_005.Input
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Group Input.002"].outputs[0],
        objectsoncurve_1.nodes["Reroute.005"].inputs[0]
    )
    # for_each_geometry_element_input_005.instance_pos -> compare_005.A
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Input.005"].outputs[2],
        objectsoncurve_1.nodes["Compare.005"].inputs[2]
    )
    # reroute_005.Output -> for_each_geometry_element_input_005.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Reroute.005"].outputs[0],
        objectsoncurve_1.nodes["For Each Geometry Element Input.005"].inputs[0]
    )
    # named_attribute_004.Attribute -> for_each_geometry_element_input_005.instance_pos
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Named Attribute.004"].outputs[0],
        objectsoncurve_1.nodes["For Each Geometry Element Input.005"].inputs[2]
    )
    # for_each_geometry_element_input_004.Element -> delete_geometry_004.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Input.004"].outputs[1],
        objectsoncurve_1.nodes["Delete Geometry.004"].inputs[0]
    )
    # points_002.Points -> for_each_geometry_element_input_001.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Points.002"].outputs[0],
        objectsoncurve_1.nodes["For Each Geometry Element Input.001"].inputs[0]
    )
    # for_each_geometry_element_output_001.Geometry -> join_geometry_002.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Output.001"].outputs[2],
        objectsoncurve_1.nodes["Join Geometry.002"].inputs[0]
    )
    # compare_006.Result -> delete_geometry_005.Selection
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Compare.006"].outputs[0],
        objectsoncurve_1.nodes["Delete Geometry.005"].inputs[1]
    )
    # for_each_geometry_element_input_006.instance_pos -> compare_006.A
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Input.006"].outputs[2],
        objectsoncurve_1.nodes["Compare.006"].inputs[2]
    )
    # group_input_004.Geometry -> for_each_geometry_element_input_006.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Group Input.004"].outputs[0],
        objectsoncurve_1.nodes["For Each Geometry Element Input.006"].inputs[0]
    )
    # named_attribute_009.Attribute -> for_each_geometry_element_input_006.instance_pos
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Named Attribute.009"].outputs[0],
        objectsoncurve_1.nodes["For Each Geometry Element Input.006"].inputs[2]
    )
    # for_each_geometry_element_input_001.Element -> delete_geometry_005.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Input.001"].outputs[1],
        objectsoncurve_1.nodes["Delete Geometry.005"].inputs[0]
    )
    # reroute_012.Output -> domain_size_001.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Reroute.012"].outputs[0],
        objectsoncurve_1.nodes["Domain Size.001"].inputs[0]
    )
    # compare_007.Result -> delete_geometry_006.Selection
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Compare.007"].outputs[0],
        objectsoncurve_1.nodes["Delete Geometry.006"].inputs[1]
    )
    # for_each_geometry_element_input_007.instance_pos -> compare_007.A
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Input.007"].outputs[2],
        objectsoncurve_1.nodes["Compare.007"].inputs[2]
    )
    # group_input_005.Geometry -> for_each_geometry_element_input_007.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Group Input.005"].outputs[0],
        objectsoncurve_1.nodes["For Each Geometry Element Input.007"].inputs[0]
    )
    # delete_geometry_006.Geometry -> for_each_geometry_element_output_007.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Delete Geometry.006"].outputs[0],
        objectsoncurve_1.nodes["For Each Geometry Element Output.007"].inputs[1]
    )
    # for_each_geometry_element_input_007.Element -> delete_geometry_006.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Input.007"].outputs[1],
        objectsoncurve_1.nodes["Delete Geometry.006"].inputs[0]
    )
    # named_attribute_010.Attribute -> for_each_geometry_element_input_007.instance_pos
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Named Attribute.010"].outputs[0],
        objectsoncurve_1.nodes["For Each Geometry Element Input.007"].inputs[2]
    )
    # for_each_geometry_element_output_007.Geometry -> attribute_statistic.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Output.007"].outputs[2],
        objectsoncurve_1.nodes["Attribute Statistic"].inputs[0]
    )
    # for_each_geometry_element_input_007.instance_size -> for_each_geometry_element_output_007.instance_size
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Input.007"].outputs[3],
        objectsoncurve_1.nodes["For Each Geometry Element Output.007"].inputs[2]
    )
    # for_each_geometry_element_output_007.instance_size -> attribute_statistic.Attribute
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Output.007"].outputs[3],
        objectsoncurve_1.nodes["Attribute Statistic"].inputs[2]
    )
    # reroute_010.Output -> math_015.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Reroute.010"].outputs[0],
        objectsoncurve_1.nodes["Math.015"].inputs[1]
    )
    # reroute_008.Output -> reroute_006.Input
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Reroute.008"].outputs[0],
        objectsoncurve_1.nodes["Reroute.006"].inputs[0]
    )
    # named_attribute_005.Attribute -> reroute_008.Input
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Named Attribute.005"].outputs[0],
        objectsoncurve_1.nodes["Reroute.008"].inputs[0]
    )
    # reroute_008.Output -> for_each_geometry_element_input_007.instance_size
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Reroute.008"].outputs[0],
        objectsoncurve_1.nodes["For Each Geometry Element Input.007"].inputs[3]
    )
    # compare_005.Result -> delete_geometry_004.Selection
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Compare.005"].outputs[0],
        objectsoncurve_1.nodes["Delete Geometry.004"].inputs[1]
    )
    # math_015.Value -> float_to_integer.Float
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Math.015"].outputs[0],
        objectsoncurve_1.nodes["Float to Integer"].inputs[0]
    )
    # float_to_integer.Integer -> points_002.Count
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Float to Integer"].outputs[0],
        objectsoncurve_1.nodes["Points.002"].inputs[0]
    )
    # math_001.Value -> store_named_attribute_003.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Math.001"].outputs[0],
        objectsoncurve_1.nodes["Store Named Attribute.003"].inputs[3]
    )
    # delete_geometry_004.Geometry -> for_each_geometry_element_output_005.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Delete Geometry.004"].outputs[0],
        objectsoncurve_1.nodes["For Each Geometry Element Output.005"].inputs[1]
    )
    # for_each_geometry_element_output_005.Geometry -> for_each_geometry_element_input_002.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Output.005"].outputs[2],
        objectsoncurve_1.nodes["For Each Geometry Element Input.002"].inputs[0]
    )
    # for_each_geometry_element_output_002.Geometry -> delete_geometry_003.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Output.002"].outputs[2],
        objectsoncurve_1.nodes["Delete Geometry.003"].inputs[0]
    )
    # store_named_attribute_003.Geometry -> for_each_geometry_element_output_002.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Store Named Attribute.003"].outputs[0],
        objectsoncurve_1.nodes["For Each Geometry Element Output.002"].inputs[1]
    )
    # for_each_geometry_element_input_002.Element -> store_named_attribute_003.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Input.002"].outputs[1],
        objectsoncurve_1.nodes["Store Named Attribute.003"].inputs[0]
    )
    # for_each_geometry_element_input_002.Index -> math_001.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Input.002"].outputs[0],
        objectsoncurve_1.nodes["Math.001"].inputs[0]
    )
    # store_named_attribute_004.Geometry -> for_each_geometry_element_output_008.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Store Named Attribute.004"].outputs[0],
        objectsoncurve_1.nodes["For Each Geometry Element Output.008"].inputs[1]
    )
    # for_each_geometry_element_input_008.Element -> store_named_attribute_004.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Input.008"].outputs[1],
        objectsoncurve_1.nodes["Store Named Attribute.004"].inputs[0]
    )
    # for_each_geometry_element_input_008.Index -> math_005.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Input.008"].outputs[0],
        objectsoncurve_1.nodes["Math.005"].inputs[0]
    )
    # delete_geometry_005.Geometry -> for_each_geometry_element_output_006.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Delete Geometry.005"].outputs[0],
        objectsoncurve_1.nodes["For Each Geometry Element Output.006"].inputs[1]
    )
    # for_each_geometry_element_output_008.Geometry -> for_each_geometry_element_output_001.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Output.008"].outputs[2],
        objectsoncurve_1.nodes["For Each Geometry Element Output.001"].inputs[1]
    )
    # for_each_geometry_element_output_006.Geometry -> for_each_geometry_element_input_008.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Output.006"].outputs[2],
        objectsoncurve_1.nodes["For Each Geometry Element Input.008"].inputs[0]
    )
    # reroute_011.Output -> math_005.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Reroute.011"].outputs[0],
        objectsoncurve_1.nodes["Math.005"].inputs[1]
    )
    # math_005.Value -> store_named_attribute_004.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Math.005"].outputs[0],
        objectsoncurve_1.nodes["Store Named Attribute.004"].inputs[3]
    )
    # reroute_009.Output -> math_001.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Reroute.009"].outputs[0],
        objectsoncurve_1.nodes["Math.001"].inputs[1]
    )
    # for_each_geometry_element_input.Sample Point Tail -> math_009.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Input"].outputs[2],
        objectsoncurve_1.nodes["Math.009"].inputs[0]
    )
    # for_each_geometry_element_input.Sample Point Head -> math_011.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Input"].outputs[3],
        objectsoncurve_1.nodes["Math.011"].inputs[0]
    )
    # math_011.Value -> sample_curve_002.Length
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Math.011"].outputs[0],
        objectsoncurve_1.nodes["Sample Curve.002"].inputs[3]
    )
    # math_009.Value -> sample_curve_003.Length
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Math.009"].outputs[0],
        objectsoncurve_1.nodes["Sample Curve.003"].inputs[3]
    )
    # attribute_statistic.Max -> reroute_009.Input
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Attribute Statistic"].outputs[4],
        objectsoncurve_1.nodes["Reroute.009"].inputs[0]
    )
    # reroute_009.Output -> reroute_010.Input
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Reroute.009"].outputs[0],
        objectsoncurve_1.nodes["Reroute.010"].inputs[0]
    )
    # reroute_010.Output -> reroute_011.Input
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Reroute.010"].outputs[0],
        objectsoncurve_1.nodes["Reroute.011"].inputs[0]
    )
    # named_attribute_002.Attribute -> math_012.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Named Attribute.002"].outputs[0],
        objectsoncurve_1.nodes["Math.012"].inputs[0]
    )
    # named_attribute_001.Attribute -> math_012.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Named Attribute.001"].outputs[0],
        objectsoncurve_1.nodes["Math.012"].inputs[1]
    )
    # math_012.Value -> math_009.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Math.012"].outputs[0],
        objectsoncurve_1.nodes["Math.009"].inputs[1]
    )
    # math_012.Value -> math_011.Value
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Math.012"].outputs[0],
        objectsoncurve_1.nodes["Math.011"].inputs[1]
    )
    # for_each_geometry_element_output_003.Geometry -> reroute_012.Input
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Output.003"].outputs[2],
        objectsoncurve_1.nodes["Reroute.012"].inputs[0]
    )
    # reroute_012.Output -> join_geometry.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["Reroute.012"].outputs[0],
        objectsoncurve_1.nodes["Join Geometry"].inputs[0]
    )
    # for_each_geometry_element_output_004.Points -> join_geometry_002.Geometry
    objectsoncurve_1.links.new(
        objectsoncurve_1.nodes["For Each Geometry Element Output.004"].outputs[2],
        objectsoncurve_1.nodes["Join Geometry.002"].inputs[0]
    )

    return objectsoncurve_1
