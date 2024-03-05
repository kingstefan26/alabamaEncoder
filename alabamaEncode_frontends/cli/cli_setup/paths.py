import hashlib
import os


def parse_paths(ctx):
    """
    Sets up the paths
    """
    ctx.output_file = os.path.abspath(ctx.output_file)
    ctx.raw_input_file = os.path.abspath(ctx.raw_input_file)

    # turn tempfolder into a full path
    ctx.output_folder = os.path.normpath(os.path.dirname(ctx.output_file) + "/")

    # derive random part from the first few letters of the sha1 hash of title
    random_part = hashlib.sha1(ctx.get_title().encode("utf-8")).hexdigest()[:5]

    ctx.temp_folder = os.path.join(ctx.output_folder, f".alabamatemp-{random_part}")
    if not os.path.exists(ctx.temp_folder):
        os.makedirs(ctx.temp_folder)

    ctx.temp_folder += "/"

    ctx.input_file = os.path.join(ctx.temp_folder, "temp.mkv")

    if not os.path.exists(ctx.raw_input_file):
        print(f"Input file {ctx.raw_input_file} does not exist")
        quit()

    # symlink input file to temp folder
    if not os.path.exists(ctx.input_file):
        os.symlink(ctx.raw_input_file, ctx.input_file)
        if not os.path.exists(ctx.input_file):
            print(f"Failed to symlink input file to {ctx.input_file}")
            quit()

    return ctx
