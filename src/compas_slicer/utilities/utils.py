import os
import json
import logging
from compas.geometry import Point, distance_point_point_sqrd, normalize_vector
from compas.geometry import Vector, closest_point_in_cloud, length_vector
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import scipy

logger = logging.getLogger('logger')

__all__ = ['get_output_directory',
           'save_to_json',
           'load_from_json',
           'save_to_text_file',
           'flattened_list_of_dictionary',
           'interrupt',
           'point_list_to_dict',
           'get_closest_mesh_vkey_to_pt',
           'get_closest_mesh_normal_to_pt',
           'get_mesh_laplacian_matrix_igl',
           'get_mesh_cotans_igl',
           'get_closest_pt_index',
           'get_closest_pt',
           'plot_networkx_graph',
           'get_mesh_vertex_coords_with_attribute',
           'get_dict_key_from_value',
           'find_next_printpoint',
           'find_previous_printpoint',
           'smooth_vectors',
           'get_normal_of_path_on_xy_plane',
           'get_all_files_with_name']


def get_output_directory(path):
    """
    Checks if a directory with the name 'output' exists in the path. If not it creates it.

    Parameters
    ----------
    path: str
        The path where the 'output' directory will be created

    Returns
    ----------
    str
        The path to the new (or already existing) 'output' directory
    """
    output_dir = os.path.join(path, 'output')
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    return output_dir


def get_closest_pt_index(pt, pts):
    """
    Finds the index of the closest point of 'pt' in the point cloud 'pts'.

    Parameters
    ----------
    pt: compas.geometry.Point3d
    pts: list, compas.geometry.Point3d

    Returns
    ----------
    int
        The index of the closest point
    """
    ci = closest_point_in_cloud(point=pt, cloud=pts)[2]
    # distances = [distance_point_point_sqrd(p, pt) for p in pts]
    # ci = distances.index(min(distances))
    return ci


def get_closest_pt(pt, pts):
    """
     Finds the closest point of 'pt' in the point cloud 'pts'.

    Parameters
    ----------
    pt: :class: 'compas.geometry.Point'
    pts: list, :class: 'compas.geometry.Point3d'

    Returns
    ----------
    compas.geometry.Point3d
        The closest point
    """
    ci = closest_point_in_cloud(point=pt, cloud=pts)[2]
    return pts[ci]


def smooth_vectors(vectors, strength, iterations):
    """
    Smooths the vector iteratively, with the given number of iterations and strength per iteration

    Parameters
    ----------
    vectors: list, :class: 'compas.geometry.Vector'
    strength: float
    iterations: int

    Returns
    ----------
    list, :class: 'compas.geometry.Vector3d'
        The smoothened vectors
    """

    for _ in range(iterations):
        for i, n in enumerate(vectors):
            if 0 < i < len(vectors) - 1:
                neighbors_average = (vectors[i - 1] + vectors[i + 1]) * 0.5
            else:
                neighbors_average = n
            vectors[i] = n * (1 - strength) + neighbors_average * strength
    return vectors


#######################################
#  json

def save_to_json(data, filepath, name):
    """
    Save the provided data to json on the filepath, with the given name

    Parameters
    ----------
    data: dict_or_list
    filepath: str
    name: str
    """

    filename = os.path.join(filepath, name)
    logger.info("Saving to json: " + filename)
    with open(filename, 'w') as f:
        f.write(json.dumps(data, indent=3, sort_keys=True))


def load_from_json(filepath, name):
    """
    Loads json from the filepath

    Parameters
    ----------
    filepath: str
    name: str
    """

    filename = os.path.join(filepath, name)
    with open(filename, 'r') as f:
        data = json.load(f)
    logger.info("Loaded json: " + filename)
    return data


#######################################
#  text file

def save_to_text_file(data, filepath, name):
    """
    Save the provided text on the filepath, with the given name

    Parameters
    ----------
    data: str
    filepath: str
    name: str
    """

    filename = os.path.join(filepath, name)
    logger.info("Saving to text file: " + filename)
    with open(filename, 'w') as f:
        f.write(data)


#######################################
#  mesh utils

def check_triangular_mesh(mesh):
    """
    Checks if the mesh is triangular. If not, then it raises an error

    Parameters
    ----------
    mesh: :class: 'compas.datastructures.Mesh'
    """

    for f_key in mesh.faces():
        vs = mesh.face_vertices(f_key)
        if len(vs) != 3:
            raise TypeError("Found a quad at face key: " + str(f_key) + " ,number of face vertices:" + str(
                len(vs)) + ". \nOnly triangular meshes supported.")


def get_closest_mesh_vkey_to_pt(mesh, pt):
    """
    Finds the vertex key that is the closest to the point.

    Parameters
    ----------
    mesh: :class: 'compas.datastructures.Mesh'
    pt: :class: 'compas.geometry.Point'

    Returns
    ----------
    int
        the closest vertex key
    """
    # cloud = [Point(data['x'], data['y'], data['z']) for v_key, data in mesh.vertices(data=True)]
    # closest_index = compas.geometry.closest_point_in_cloud(pt, cloud)[2]
    vertex_tupples = [(v_key, Point(data['x'], data['y'], data['z'])) for v_key, data in mesh.vertices(data=True)]
    vertex_tupples = sorted(vertex_tupples, key=lambda v_tupple: distance_point_point_sqrd(pt, v_tupple[1]))
    closest_vkey = vertex_tupples[0][0]
    return closest_vkey


def get_closest_mesh_normal_to_pt(mesh, pt):
    """
    Finds the closest vertex normal to the point.

    Parameters
    ----------
    mesh: :class: 'compas.datastructures.Mesh'
    pt: :class: 'compas.geometry.Point'

    Returns
    ----------
    :class: 'compas.geometry.Vector'
        The closest normal of the mesh.

    """

    closest_vkey = get_closest_mesh_vkey_to_pt(mesh, pt)
    v = mesh.vertex_normal(closest_vkey)
    return Vector(v[0], v[1], v[2])


def get_mesh_vertex_coords_with_attribute(mesh, attr, value):
    """
    Finds the coordinates of all the vertices that have an attribute with key=attr that equals the value.

    Parameters
    ----------
    mesh: :class: 'compas.datastructures.Mesh'
    attr: str
    value: anything that can be stored into a dictionary

    Returns
    ----------
    list, :class: 'compas.geometry.Point'
        the closest vertex key
    """

    pts = []
    for vkey, data in mesh.vertices(data=True):
        if data[attr] == value:
            pts.append(Point(*mesh.vertex_coordinates(vkey)))
    return pts


def get_normal_of_path_on_xy_plane(k, point, path, mesh):
    """
    Finds the normal of the curve that lies on the xy plane at the point with index k

    Parameters
    ----------
    k: int, index of the point
    point: :class: 'compas.geometry.Point'
    path: :class: 'compas_slicer.geometry.Path'
    mesh: :class: 'compas.datastructures.Mesh'

    Returns
    ----------
    :class: 'compas.geometry.Vector'
    """

    # find mesh normal is not really needed in the 2D case of planar slicer
    # instead we only need the normal of the curve based on the neighboring pts
    if (0 < k < len(path.points) - 1) or path.is_closed:
        prev_pt = path.points[k - 1]
        next_pt = path.points[(k + 1) % len(path.points)]
        v1 = np.array(normalize_vector(Vector.from_start_end(prev_pt, point)))
        v2 = np.array(normalize_vector(Vector.from_start_end(point, next_pt)))
        v = (v1 + v2) * 0.5
        normal = [-v[1], v[0], v[2]]  # rotate 90 degrees COUNTER-clockwise on the xy plane

    else:
        if k == 0:
            next_pt = path.points[k + 1]
            v = normalize_vector(Vector.from_start_end(point, next_pt))
            normal = [-v[1], v[0], v[2]]  # rotate 90 degrees COUNTER-clockwise on the xy plane
        else:  # k == len(path.points)-1:
            prev_pt = path.points[k - 1]
            v = normalize_vector(Vector.from_start_end(point, prev_pt))
            normal = [v[1], -v[0], v[2]]  # rotate 90 degrees clockwise on the xy plane

    if length_vector(normal) == 0:
        # When the neighboring elements happen to cancel out, then search for the true normal,
        # and project it on the xy plane for consistency
        normal = get_closest_mesh_normal_to_pt(mesh, point)
        normal = [normal[0], normal[1], 0]

    normal = normalize_vector(normal)
    normal = Vector(*list(normal))
    return normal


#######################################
# igl utils

def get_mesh_laplacian_matrix_igl(mesh, fix_boundaries=True):
    """
    Gets the laplace operator of the mesh

    Parameters
    ----------
    mesh: :class: 'compas.datastructures.Mesh'
    fix_boundaries: bool

    Returns
    ----------
    :class: 'scipy.sparse.csr_matrix'
        sparse matrix (dimensions: #V x #V), laplace operator, each row i corresponding to v(i, :)
    """
    import igl
    logger.info('Getting laplacian matrix, fix boundaries : ' + str(fix_boundaries))
    v, f = mesh.to_vertices_and_faces()
    L = igl.cotmatrix(np.array(v), np.array(f))

    if fix_boundaries:
        # fix boundaries by putting the corresponding columns of the sparse matrix to 0
        L_dense = L.toarray()
        for i, (vkey, data) in enumerate(mesh.vertices(data=True)):
            if data['boundary'] > 0:
                L_dense[i][:] = np.zeros(len(v))
        L = scipy.sparse.csr_matrix(L_dense)
    return L


def get_mesh_cotans_igl(mesh):
    """
    Gets the cotangent entries of the mesh


    Parameters
    ----------
    mesh: :class: 'compas.datastructures.Mesh'

    Returns
    ----------
    :class: 'np.array'
        Dimensions: F by 3 list of 1/2*cotangents corresponding angles
    """
    import igl
    v, f = mesh.to_vertices_and_faces()
    return igl.cotmatrix_entries(np.array(v), np.array(f))


#######################################
#  networkx graph

def plot_networkx_graph(G):
    """
    Plots the graph G

    Parameters
    ----------
    G: networkx.Graph
    """

    plt.subplot(121)
    nx.draw(G, with_labels=True, font_weight='bold', node_color=range(len(list(G.nodes()))))
    plt.show()


#######################################
#  dict utils

def point_list_to_dict(pts_list):
    """
    Turns a list of compas.geometry.Point into a dictionary, so that it can be saved to Json.

    Parameters
    ----------
    pts_list: list, :class:`compas.geometry.Point`

    Returns
    ----------
    dict
    """

    data = {}
    for i in range(len(pts_list)):
        data[i] = list(pts_list[i])
    return data


#  --- Flattened list of dictionary
def flattened_list_of_dictionary(dictionary):
    """
    Turns the dictionary into a flat list

    Parameters
    ----------
    dictionary: dict

    Returns
    ----------
    list
    """

    flattened_list = []
    for key in dictionary:
        [flattened_list.append(item) for item in dictionary[key]]
    return flattened_list


def get_dict_key_from_value(dictionary, val):
    """
    Return the key of a dictionary that stores the val

    Parameters
    ----------
    dictionary: dict
    val: anything that can be stored in a dictionary
    """

    for key in dictionary:
        value = dictionary[key]
        if val == value:
            return key
    return "key doesn't exist"


def find_next_printpoint(pp_dict, layer_key, path_key, i, j, k):
    """
    Returns the next printpoint from the current printpoint if it exists, otherwise returns None.
    """
    next_ppt = None
    if k < len(pp_dict[layer_key][path_key]) - 1:  # If there are more ppts in the current path, then take the next ppt
        next_ppt = pp_dict[layer_key][path_key][k + 1]
    else:
        if j < len(pp_dict[layer_key]) - 1:  # Otherwise take the next path if there are more paths in the current layer
            next_ppt = pp_dict[layer_key]['path_%d' % (j + 1)][0]
        else:
            if i < len(pp_dict) - 1:  # Otherwise take the next layer if there are more layers in the current slicer
                next_ppt = pp_dict['layer_%d' % (i + 1)]['path_0'][0]
    return next_ppt


def find_previous_printpoint(pp_dict, layer_key, path_key, i, j, k):
    """
    Returns the previous printpoint from the current printpoint if it exists, otherwise returns None.
    """
    prev_ppt = None
    if k > 0:  # If not the first point in a path, take the previous point in the path
        prev_ppt = pp_dict[layer_key][path_key][k - 1]
    else:
        if j > 0:  # Otherwise take the last point of the previous path, if there are more paths in the current layer
            prev_ppt = pp_dict[layer_key]['path_%d' % (j - 1)][-1]
        else:
            if i > 0:  # Otherwise take the last path of the previous layer if there are more layers in the current slicer
                last_path_key = len(pp_dict[layer_key]) - 1
                prev_ppt = pp_dict['layer_%d' % (i - 1)]['path_%d' % (last_path_key)][-1]
    return prev_ppt


#######################################
#  control flow

def interrupt():
    """
    Interrupts the flow of the code while it is running.
    It asks for the user to press a enter to continue or abort.
    """

    value = input("Press enter to continue, Press 1 to abort ")
    print("")
    if isinstance(value, str):
        if value == '1':
            raise ValueError("Aborted")


#######################################
#  load all files with name

def get_all_files_with_name(startswith, endswith, DATA_PATH):
    """
    Finds all the filenames in the DATA_PATH that start and end with the provided strings

    Parameters
    ----------
    startswith: str
    endswith: str
    DATA_PATH: str

    Returns
    ----------
    list, str
        All the filenames
    """

    files = []
    for file in os.listdir(DATA_PATH):
        if file.startswith(startswith) and file.endswith(endswith):
            files.append(file)
    print('')
    logger.info('Reloading : ' + str(files))
    return files


if __name__ == "__main__":
    pass
