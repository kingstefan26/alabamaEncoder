import os


def get_probe_file_base(encoded_scene_path) -> str:
    """
    A helper function to get the a probe file path derived from the encoded scene path

    Examples:
    /home/test/out/temp/1.ivf -> /home/test/out/temp/1_rate_probes/
    /home/test/out/temp/42.ivf -> /home/test/out/temp/42_rate_probes/
    /home/test/out/temp/filename.ivf -> /home/test/out/temp/filename_rate_probes/
    """
    # get base file name without an extension
    file_without_extension = os.path.splitext(os.path.basename(encoded_scene_path))[0]

    # temp folder
    path_without_file = os.path.dirname(encoded_scene_path)

    # join
    probe_folder_path = os.path.join(
        path_without_file, (file_without_extension + "_rate_probes")
    )

    # add trailing slash
    probe_folder_path += os.path.sep

    os.makedirs(probe_folder_path, exist_ok=True)
    # new file base
    return probe_folder_path
