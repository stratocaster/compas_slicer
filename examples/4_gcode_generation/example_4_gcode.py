import time
import os
import logging

import compas_slicer.utilities as utils
from compas_slicer.pre_processing import move_mesh_to_point
from compas_slicer.slicers import PlanarSlicer
from compas_slicer.post_processing import generate_brim
from compas_slicer.post_processing import simplify_paths_rdp
from compas_slicer.post_processing import seams_smooth
from compas_slicer.print_organization import PlanarPrintOrganizer
from compas_slicer.print_organization import set_extruder_toggle
from compas_slicer.print_organization import add_safety_printpoints
from compas_slicer.print_organization import set_linear_velocity
from compas_slicer.print_organization import set_blend_radius
from compas_slicer.utilities import save_to_json
from compas_viewers.objectviewer import ObjectViewer

from compas.datastructures import Mesh
from compas.geometry import Point

logger = logging.getLogger('logger')
logging.basicConfig(format='%(levelname)s-%(message)s', level=logging.INFO)

DATA = os.path.join(os.path.dirname(__file__), 'data')
OUTPUT_DIR = utils.get_output_directory(DATA)  # creates 'output' folder if it doesn't already exist
MODEL = 'simple_vase_open_low_res.obj'


def main():

    compas_mesh = Mesh.from_obj(os.path.join(DATA, MODEL))
    move_mesh_to_point(compas_mesh, Point(0, 0, 0))

    # ----- slicing
    slicer = PlanarSlicer(compas_mesh, slicer_type="cgal", layer_height=4.5)
    slicer.slice_model()
    generate_brim(slicer, layer_width=3.0, number_of_brim_offsets=4)
    simplify_paths_rdp(slicer, threshold=0.6)
    seams_smooth(slicer, smooth_distance=10)
    slicer.printout_info()
    save_to_json(slicer.to_data(), OUTPUT_DIR, 'slicer_data.json')

    # ----- print organization
    print_organizer = PlanarPrintOrganizer(slicer)
    print_organizer.create_printpoints()
    # Set fabrication-related parameters
    set_extruder_toggle(print_organizer, slicer)
    set_linear_velocity(print_organizer, "constant", v=25.0)
    print_organizer.printout_info()

    # create and output gcode
    gcode_parameters = {}
    gcode_text = print_organizer.output_gcode(gcode_parameters)
    utils.save_to_text_file(gcode_text, OUTPUT_DIR, 'my_gcode.gcode')


if __name__ == "__main__":
    main()
