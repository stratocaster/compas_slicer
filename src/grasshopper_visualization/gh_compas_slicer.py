import os
import json
import rhinoscriptsyntax as rs
from compas.datastructures import Mesh
import Rhino.Geometry as rg
from compas_ghpython.artists import MeshArtist
from compas.geometry import Frame


#######################################
# --- Slicer

def load_slicer(path, folder_name, json_name):
    """ Loads slicer data. """
    data = load_json_file(path, folder_name, json_name)

    mesh = None
    paths = []
    are_closed = []
    all_points = []

    if data:

        if 'mesh' in data:
            compas_mesh = Mesh.from_data(data['mesh'])
            artist = MeshArtist(compas_mesh)
            mesh = artist.draw()
        else:
            print('No mesh has been saved in the json file.')

        if 'layers' in data:
            layers_data = data['layers']

            for i in range(len(layers_data)):
                layer_data = layers_data[str(i)]
                paths_data = layer_data['paths']

                for j in range(len(paths_data)):
                    path_data = paths_data[str(j)]
                    pts = []

                    are_closed.append(path_data['is_closed'])

                    for k in range(len(path_data['points'])):
                        pt = path_data['points'][str(k)]
                        pt = rs.AddPoint(pt[0], pt[1], pt[2])  # re-create points
                        pts.append(pt)
                    all_points.extend(pts)
                    path = rs.AddPolyline(pts)

                    # # create contour per layer
                    # try:
                    #     path = rs.AddPolyline(pts)
                    # except:
                    #     print('Attention! Could not add polyline at layer %d, path %d with %d points ' % (
                    #         i, j, len(path_data['points'])))

                    paths.append(path)
        else:
            print('No layers have been saved in the json file. Is this the correct json?')

    return mesh, paths, are_closed, all_points


#######################################
# --- Printpoints

def load_printpoints(path, folder_name, json_name):
    """ Loads a dict of compas_slicer printpoints. """
    data = load_json_file(path, folder_name, json_name)

    # geometry data
    points = []
    frames = []
    layer_heights = []
    up_vectors = []
    mesh_normals = []
    closest_support = []

    # fabrication related data
    velocities = []
    wait_times = []
    blend_radiuses = []
    extruder_toggles = []
    feasibility = []

    if data:
        for i in range(len(data)):
            data_point = data[str(i)]

            # geometry related data
            point = rg.Point3d(data_point["point"][0], data_point["point"][1], data_point["point"][2])
            points.append(point)

            compas_frame = Frame.from_data(data_point["frame"])
            pt, x_axis, y_axis = compas_frame.point, compas_frame.xaxis, compas_frame.yaxis
            frame = rs.PlaneFromNormal(pt, rs.VectorCrossProduct(rg.Vector3d(x_axis[0], x_axis[1], x_axis[2]),
                                                                 rg.Vector3d(y_axis[0], y_axis[1], y_axis[2])))
            frames.append(frame)

            layer_heights.append(data_point["layer_height"])

            v = data_point["up_vector"]
            up_vector = rg.Vector3d(v[0], v[1], v[2])
            up_vectors.append(up_vector)

            v = data_point["mesh_normal"]
            mesh_normal = rg.Vector3d(v[0], v[1], v[2])
            mesh_normals.append(mesh_normal)

            cp = data_point["closest_support_pt"]
            if cp:
                cp_pt = rg.Point3d(cp[0], cp[1], cp[2])
                closest_support.append(cp_pt)

            # fabrication related data
            velocities.append(data_point["velocity"])
            wait_times.append(data_point["wait_time"])
            blend_radiuses.append(data_point["blend_radius"])
            extruder_toggles.append(data_point["extruder_toggle"])
            feasibility.append(data_point["is_feasible"])

    return points, frames, layer_heights, up_vectors, mesh_normals, closest_support, velocities, wait_times, \
        blend_radiuses, extruder_toggles, feasibility


#######################################
# --- Lightweight path visualization

def lightweight_path_visualization(points, extruder_toggles, domain_start, domain_end, diameter, pipe_resolution):
    """ Visualize print paths with simple lines or pipes. """
    #  check input
    assert len(points) == len(extruder_toggles), \
        'Wrong length of input lists'

    print_path_pipes = []
    travel_path_lines = []

    domain_end = min(domain_end, len(points))  # make sure domain_end does not exceed len of pts

    points = points[domain_start:domain_end]
    extruder_toggles = extruder_toggles[domain_start:domain_end]
    for i in range(len(points) - 1):
        if extruder_toggles[i]:
            line = rg.Curve.CreateControlPointCurve([points[i], points[i + 1]])  # create line
            pipe = rg.Mesh.CreateFromCurvePipe(line, diameter / 2, pipe_resolution, 1, 0, True)
            print_path_pipes.append(pipe)
        else:
            line = rg.Curve.CreateControlPointCurve([points[i], points[i + 1]])
            travel_path_lines.append(line)  # add to travel path list

    return print_path_pipes, travel_path_lines


#######################################
# --- Render path visualization

def render_path_visualization(points, mesh_normals, layer_heights, up_vectors, extruder_toggles, cross_section,
                              planar_printing):
    """ Visualize print paths with simple loft surfaces. """

    # check input
    assert len(points) == len(mesh_normals) == len(layer_heights) == len(up_vectors) == len(extruder_toggles), \
        'Wrong length of input lists'

    loft_surfaces = []
    travel_path_lines = []

    if points[0] and mesh_normals[0] and layer_heights[0] and up_vectors[0]:  # check if any of the values are None

        if planar_printing:  # then make sure that all normals lie on the xy plane
            for n in mesh_normals:
                n[2] = 0

        # transform and scale cross sections accordingly
        cen = rs.CurveAreaCentroid(cross_section)[0]
        origin_plane = rg.Plane(cen, rg.Vector3d(1, 0, 0), rg.Vector3d(0, 0, 1))

        target_planes = []
        for i, pt in enumerate(points):
            target_plane = rg.Plane(pt, mesh_normals[i], up_vectors[i])
            target_planes.append(target_plane)

        cross_sections = []
        for h, target_plane in zip(layer_heights, target_planes):
            section = rs.ScaleObject(rs.CopyObject(cross_section), origin=cen, scale=[0.9 * h, 1, 0.9 * h])
            T = rg.Transform.PlaneToPlane(origin_plane, target_plane)
            rs.TransformObject(section, T)
            cross_sections.append(section)

        loft_surfaces = []
        travel_path_lines = []

        for i in range(len(points) - 1):
            if extruder_toggles[i]:
                loft = rs.AddLoftSrf([cross_sections[i], cross_sections[i + 1]])
                if loft:
                    loft_surfaces.append(loft[0])
            else:
                line = rg.Curve.CreateControlPointCurve([points[i], points[i + 1]])
                travel_path_lines.append(line)  # add to travel path list

    else:
        print('At least one of the inputs that you have provided are invalid. ')

    return loft_surfaces, travel_path_lines


#######################################
# --- Tool visualization

def tool_visualization(origin_coords, mesh, planes, i):
    """ Visualize example tool motion. """

    i = min(i, len(planes) - 1)  # make sure i doesn't go beyond available number of planes
    passed_path = None

    if planes[0]:
        origin = [float(origin_coords[0]), float(origin_coords[1]), float(origin_coords[2])]
        o = rg.Point3d(origin[0], origin[1], origin[2])
        x = rg.Vector3d(1, 0, 0)
        z = rg.Vector3d(0, 0, -1)

        ee_frame = rg.Plane(o, x, z)
        target_frame = planes[i]

        T = rg.Transform.PlaneToPlane(ee_frame, target_frame)
        mesh = rs.TransformObject(rs.CopyObject(mesh), T)

        passed_path = rs.AddPolyline([plane.Origin for plane in planes[:i + 1]])

    else:
        print('The planes you have provided are invalid. ')

    return mesh, passed_path


#######################################
# --- Create_targets (Curved slicing)

def create_targets(mesh, targets, resolution_mult, path, folder_name, json_name):
    """ Creation of targets for curved slicing. """

    avg_face_area = max(rs.MeshArea([mesh])) / rs.MeshFaceCount(mesh)
    div_num = max(20, int(resolution_mult * avg_face_area))

    pts = []
    for target in targets:
        print(div_num)
        pts.extend(rs.DivideCurve(target, div_num))

    vs = rs.MeshVertices(mesh)
    vertices = []
    vertex_indices = []
    for p in pts:
        closest_vi = get_closest_point_index(p, vs)
        if closest_vi not in vertex_indices:
            ds_from_targets = [distance_of_pt_from_crv(vs[closest_vi], target) for target in targets]
            if min(ds_from_targets) < 1:  # hardcoded threshold value
                vertices.append(vs[closest_vi])
                vertex_indices.append(closest_vi)

    save_json_file(vertex_indices, path, folder_name, json_name)
    return pts, vertices, vertex_indices


#######################################
# --- Create_targets (Curved slicing)

def load_multiple_meshes(starts_with, ends_with, path, folder_name):
    """ Load all the meshes that have the specified name, and print them in different colors. """
    filenames = get_files_with_name(starts_with, ends_with, os.path.join(path, folder_name, 'output'))
    meshes = [Mesh.from_obj(os.path.join(path, folder_name, 'output', filename)) for filename in filenames]

    loaded_meshes = []
    for i, m in enumerate(meshes):
        artist = MeshArtist(m)
        color = get_color(i, total=len(meshes))
        mesh = artist.draw(color)
        loaded_meshes.append(mesh)

    return loaded_meshes


#######################################
# --- Load json points

def load_json_points(path, folder_name, json_name):
    """
    Loads a json file that stores a dictionary of N points in the format:
    data['0']=[x0,y0,z0], ...,  data['N']=[xN,yN,zN]
    """
    data = load_json_file(path, folder_name, json_name)
    points = None

    if data:
        points = []
        for i in range(len(data)):
            points.append(rg.Point3d(data[str(i)][0], data[str(i)][1], data[str(i)][2]))
    return points


#######################################
# --- Load json vectors

def load_json_vectors(path, folder_name, json_name):
    """
    Loads a json file from the 'output' folder,
    that stores a vector field in the format:
    data['0']=[x0,y0,z0], ...,  data['N']=[xN,yN,zN]
    """
    data = load_json_file(path, folder_name, json_name)
    vectors = None

    if data:
        vectors = []
        for i in range(len(data)):
            vectors.append(rg.Vector3d(data[str(i)][0], data[str(i)][1], data[str(i)][2]))
    return vectors


#######################################
# --- Load json polylines

def load_json_polylines(path, folder_name, json_name):
    """
    Loads a json file that stores a dictionary of N polylines in the format:
    data['0']=points_dict_0, ..., data['N'] = points_dict_N, where points_dict is in the format:
    points_dict['0']=[x0,y0,z0], ...,  points_dict['N']=[xN,yN,zN]
    """
    data = load_json_file(path, folder_name, json_name)
    all_points = []
    polylines = []

    if data:
        for i in range(len(data)):
            pts = []
            pts_dict = data[str(i)]

            for j in range(len(pts_dict)):
                p = pts_dict[str(j)]
                pts.append(rg.Point3d(p[0], p[1], p[2]))
            all_points.extend(pts)
            polylines.append(rs.AddPolyline(pts))

    return polylines, all_points


#######################################
# --- Load json BaseBoundaries

def load_base_boundaries(path, folder_name, json_name):
    """
    Loads a json file that stores a dictionary of BaseBoundary classes in the format:
    data['0']=base_boundary_1.to_data(), ..., data['N']=base_boundary_N.to_data()
    """
    data = load_json_file(path, folder_name, json_name)
    points, vectors, number_of_boundaries = [], [], None

    if data:
        number_of_boundaries = len(data)

        for i in range(len(data)):
            p = data[str(i)]['points']
            v = data[str(i)]['up_vectors']

            points.extend([rg.Point3d(p[key][0], p[key][1], p[key][2]) for key in p])
            vectors.extend([rg.Vector3d(v[key][0], v[key][1], v[key][2]) for key in v])

    return points, vectors, number_of_boundaries


#######################################
# --- Load json BaseBoundaries

def distance_fields_interpolation(path, folder_name, json_name1, json_name2, weight):
    """ Simple interpolation of the distance fields that are stored in the two json files. """
    distances_LOW = load_json_file(path, folder_name, json_name1)
    distances_HIGH = load_json_file(path, folder_name, json_name2)

    if distances_LOW and distances_HIGH:
        assert (len(distances_LOW) == len(distances_HIGH)), 'Wrong number of distances provided. '
        return [d2 * weight - d1 * (1 - weight) for d1, d2 in zip(distances_LOW, distances_HIGH)]


#######################################
# --- Load json BaseBoundaries

def distance_fields_weighted_interpolation(path, folder_name, json_name, weight):
    """ Weighted interpolation of the two distance fields in the json file. """
    data = load_json_file(path, folder_name, json_name)
    interpolation = []

    if data:
        distances_LOW = data['distances_LOW']
        distances_HIGH_dict = data['distances_HIGH_clusters']
        t_ends_HIGH = data['t_end_per_cluster_HIGH']
        has_blend_union = data['has_blend_union_HIGH']
        blend_radius = data['blend_radius']

        weights_remapped = [remap_unbound(weight, 0, t_end, 0, 1) for t_end in t_ends_HIGH]

        for i in range(len(distances_LOW)):
            d_low = distances_LOW[i]
            ds_high = [distances_HIGH_dict[str(j)][i] for j in range(len(distances_HIGH_dict))]

            ds = [(w - 1) * d_low + w * d_high for d_high, w in zip(ds_high, weights_remapped)]

            if has_blend_union:
                d_final = blend_union_list(ds, blend_radius)
            else:
                d_final = min(ds)
            interpolation.append(abs(d_final))

    return interpolation


##############################################
# --- utilities
##############################################

def missing_input():
    """ Deals with cases where the user has not defined all the necessary inputs. """
    print('Please provide all the inputs')


def load_json_file(path, folder_name, json_name):
    """ Loads data from json. """

    filename = os.path.join(os.path.join(path), folder_name, 'output', json_name)
    data = None

    if os.path.isfile(filename):
        with open(filename, 'r') as f:
            data = json.load(f)
        print("Loaded Json: '" + filename + "'")
    else:
        print("Attention! Filename: '" + filename + "' does not exist. ")

    return data


def save_json_file(data, path, folder_name, json_name):
    """ Saves data to json. """
    filename = os.path.join(path, folder_name, json_name)
    with open(filename, 'w') as f:
        f.write(json.dumps(data, indent=3, sort_keys=True))
    print("Saved to Json: '" + filename + "'")


def get_closest_point_index(pt, pts):
    """ Closest point index of the pts from pt. """
    distances = [rs.Distance(p, pt) for p in pts]
    min_index = distances.index(min(distances))
    return min_index


def distance_of_pt_from_crv(pt, crv):
    """ Smallest distance from point to curve. """
    param = rs.CurveClosestPoint(crv, pt)
    cp = rs.EvaluateCurve(crv, param)
    return rs.Distance(pt, cp)


def get_files_with_name(startswith, endswith, DATA_PATH):
    """ Find all files with the specified start and end in the data path. """
    files = []
    for file in os.listdir(DATA_PATH):
        if file.startswith(startswith) and file.endswith(endswith):
            files.append(file)
    print('Found %d files with the given criteria : ' % len(files) + str(files))
    return files


def get_color(i, total):
    """ Returns a color per index interpolating the colorspace of 5 colors that are hardcoded (c1 .. c5). """
    i, total = float(i), float(total)

    c1 = rg.Vector3d(234, 38, 0.0)  # 0.00
    c2 = rg.Vector3d(234, 126, 0.0)  # 0.25
    c3 = rg.Vector3d(254, 244, 84)  # 0.50
    c4 = rg.Vector3d(173, 203, 249)  # 0.75
    c5 = rg.Vector3d(75, 107, 169)  # 1.00

    a = (i / (total - 1)) * 4.0
    if 0.0 <= a < 1:
        c_left, c_right = c1, c2
    elif 1 <= a < 2:
        c_left, c_right = c2, c3
        a -= 1
    elif 2 <= a < 3:
        c_left, c_right = c3, c4
        a -= 2
    else:
        c_left, c_right = c4, c5
        a -= 3

    weight = a
    c = (1 - weight) * c_left + weight * c_right
    return [int(c[0]), int(c[1]), int(c[2])]


def remap_unbound(input_val, in_from, in_to, out_from, out_to):
    """ Remap numbers without clamping values. """
    out_range = out_to - out_from
    in_range = in_to - in_from
    in_val = input_val - in_from
    val = (float(in_val) / in_range) * out_range
    out_val = out_from + val
    return out_val


def blend_union_list(values, r):
    """ Returns a blend union of the elements of the list, with blend radius r. """
    d_result = 9999999  # very big number
    for d in values:
        d_result = blend_union(d_result, d, r)
    return d_result


def blend_union(da, db, r):
    """ Blend union of the distances da, db with blend radius r. """
    e = max(r - abs(da - db), 0)
    return min(da, db) - e * e * 0.25 / r


if __name__ == "__main__":
    pass
