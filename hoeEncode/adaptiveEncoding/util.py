import copy
import os


def get_probe_file_base(encoded_scene_path, temp_folder) -> str:
    """
    This filename will be used to craete grain/rate probes
    eg:
    if filename is "./test/1.ivf"
    then ill create
    "./test/1_rate_probes/probe.bitrate.speed12.grain0.ivf"
    "./test/1_rate_probes/probe.bitrate.speed12.grain1.ivf"
    "./test/1_rate_probes/probe.grain0.speed12.avif"
    etc
    """
    encoded_scene_path = copy.deepcopy(encoded_scene_path)
    path_without_file = os.path.dirname(encoded_scene_path)
    filename = os.path.basename(encoded_scene_path)
    filename_without_ext = os.path.splitext(filename)[0]
    # new folder for the rate probes
    probe_folder_path = os.path.join(temp_folder, path_without_file,
                                     filename_without_ext + '_rate_probes')
    # make the folder
    os.makedirs(probe_folder_path, exist_ok=True)
    # new file base
    return os.path.join(probe_folder_path, filename_without_ext)