import os


def run_post_encode_cleanup(ctx):
    # TODO cleanup right in multiencode
    print("Cleaning up temp folder 🥺")
    for root, dirs, files in os.walk(ctx.temp_folder):
        # remove all folders that contain 'rate_probes'
        for name in dirs:
            if "rate_probes" in name:
                # remove {rate probe folder}/*.ivf
                for root2, dirs2, files2 in os.walk(ctx.temp_folder + name):
                    for name2 in files2:
                        if name2.endswith(".ivf"):
                            os.remove(ctx.temp_folder + name + "/" + name2)
        # remove all *.stat files in tempfolder
        for name in files:
            if name.endswith(".stat"):
                # try to remove
                os.remove(ctx.temp_folder + name)
    # clean empty folders in the temp folder
    for root, dirs, files in os.walk(ctx.temp_folder):
        for name in dirs:
            if len(os.listdir(os.path.join(root, name))) == 0:
                os.rmdir(os.path.join(root, name))
    return ctx
