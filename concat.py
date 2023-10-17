import argparse
import os
import subprocess
import sys

from tqdm import tqdm

from alabamaEncode.utils.ffmpegUtil import get_video_lenght

# example usage:
# python genConcat.py out.mp4
# python genConcat.py Epic.mkv ./temp/

# Command line arguments
parser = argparse.ArgumentParser(
    prog="Concater",
    description="Concatenate all .ivf files in a directory",
    epilog="""Example usage:
                    python concat.py out.mp4
                    python concat.py Epic.mkv ./temp/""",
)
parser.add_argument("output", help="Output file name")
# optional temp dir
parser.add_argument(
    "temp_dir",
    help="Temp directory",
    nargs="?",
    default="temp/",
    type=str,
    metavar="temp_dir",
)

# optinal flag that muxes the audio
parser.add_argument("-a", "--audio", help="Mux audio", action="store_true")

# max .ivf index number
parser.add_argument(
    "-m", "--max", help="Max .ivf index number", type=int, default=-1, metavar="max"
)

args = parser.parse_args()

mux_audio = args.audio

# output file name
output = args.output

# temp dir
tmp_dir = args.temp_dir

# if output is not set, quit
if output == "" or output is None:
    print("Output file name not set")
    sys.exit(1)

print("Output file name: " + output)

# make sure the temp dir ends with a slash
if tmp_dir[-1] != "/":
    tmp_dir += "/"

# make sure the temp dir doesn't start with a slash
if tmp_dir[0] == "/":
    tmp_dir = tmp_dir[1:]

# make sure the directory exists
if not os.path.exists(tmp_dir):
    print(f"Directory {tmp_dir} does not exist")
    sys.exit(1)

# make sure the directory is not empty
if not os.listdir(tmp_dir):
    print(f"Directory {tmp_dir} is empty")
    sys.exit(1)

# list of file names so we can sort alphabetically later
file_names = []

# list of invalid files so the user can delete them
invalid_files = []

for name in tqdm(os.listdir(tmp_dir), desc="Checking files"):
    if name.endswith(".ivf"):
        # get the file name
        name = name[:-4]

        # check if the filename is a number
        if name.isdigit():
            number_name = int(name)
            # if the max flag is set and the number is greater than the max then skip it
            if args.max != -1 and number_name > args.max:
                continue

        # add name to list
        file_names.append(name)
        # run ffmpeg command that checks if the file is valid
        # ffmpeg -v error -i $i -c copy -f null -
        argv_ = f'ffmpeg -v error -i "{tmp_dir}{name}.ivf" -c copy -f null -'
        # if the command has any output then the file is invalid
        p = subprocess.Popen(
            argv_,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        p.wait()
        proc_output = p.stdout.read()
        if len(proc_output) > 0:
            tqdm.write(f"Found invalid file: {name}.ivf")
            invalid_files.append(name)

# if there are invalid files, print them out
if len(invalid_files) > 0:
    # red text
    print("\033[91m", end="")
    print(f"Found invalid files")
    print("To remove run:")
    # assamble the command to remove the invalid files
    command = "rm "
    for name in invalid_files:
        command += f"{tmp_dir}{name}.ivf "
    print(command)
    quit()

# treat the names like numbers and sort them
file_names.sort(key=lambda f: int("".join(filter(str.isdigit, f))))

with open("mhmconcat", "w") as f:
    for name in file_names:
        f.write(f"file '{tmp_dir}{name}.ivf'\n")

# if the audio flag is set, then mux the audio
if mux_audio:
    print("muxing audio innt luv")

    kumannds = []

    output_ = f'ffmpeg -v error -f concat -safe 0 -i mhmconcat -movflags +faststart -c:v copy "temp_{output}"'
    print("Running command: " + output_)
    os.system(output_)

    video_length = get_video_lenght(f"temp_{output}")

    kumannds.append(
        f'ffmpeg -v error -i "temp_{output}" -i "{tmp_dir}temp.mkv" -map 0:v -map 1:a -c:a libopus -ac 2 '
        f'-b:a 70k -vbr on -movflags +faststart -c:v copy -t {video_length} "ttemp_{output}"'
    )

    # second command that uses mkvmerge to write additional metadata & fixup the container
    kumannds.append(f'mkvmerge -o "{output}" "ttemp_{output}"')

    # remove temp
    kumannds.append(f'rm "temp_{output}"')
    kumannds.append(f'rm "ttemp_{output}"')

    for command in kumannds:
        print("Running: " + command)
        os.system(command)
else:
    print("not muxing audio")
    argv_ = f'ffmpeg -v error -f concat -safe 0 -i mhmconcat -c copy "{output}"'
    print("Running: " + argv_)
    os.system(argv_)
    print("Removing mhmconcat")
    os.system("rm mhmconcat")
