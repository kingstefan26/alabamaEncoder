import argparse
import os
import subprocess
import sys

from tqdm import tqdm

from alabamaEncode.core.bin_utils import get_binary
from alabamaEncode.core.ffmpeg import Ffmpeg
from alabamaEncode.core.path import PathAlabama

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

parser.add_argument("-e", help="extension of files to concat", type=str, default="ivf")

parser.add_argument("--start_offset", help="start offset", type=int, default=0)

args = parser.parse_args()

mux_audio = args.audio

# output file name
output = args.output

ext = args.e

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
    if name.endswith(f".{ext}"):
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
        argv_ = f'ffmpeg -v error -i "{tmp_dir}{name}.{ext}" -c copy -f null -'
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
            tqdm.write(f"Found invalid file: {name}.{ext}")
            invalid_files.append(name)

for i in range(args.max):
    if str(i) not in file_names:
        tqdm.write(f"Missing file: {i}.{ext}")
        invalid_files.append(str(i))

# if there are invalid files, print them out
if len(invalid_files) > 0:
    # red text
    print("\033[91m", end="")
    print(f"Found invalid files")
    print("To remove run:")
    # assamble the command to remove the invalid files
    command = "rm "
    for name in invalid_files:
        command += f"{tmp_dir}{name}.{ext} "
    print(command)
    quit()


# treat the names like numbers and sort them
file_names.sort(key=lambda f: int("".join(filter(str.isdigit, f))))

with open("mhmconcat", "w") as f:
    for name in file_names:
        f.write(f"file '{tmp_dir}{name}.{ext}'\n")

# if the audio flag is set, then mux the audio
if mux_audio:
    print("muxing audio innt luv")

    output_ = f'ffmpeg -v error -f concat -safe 0 -i mhmconcat -movflags +faststart -c:v copy "{output}.TEMP.mkv"'
    print("Running command: " + output_)
    os.system(output_)

    video_length = Ffmpeg.get_video_length(PathAlabama(f"{output}.TEMP.mkv"))

    offset = f"-ss {args.start_offset}" if args.start_offset != 0 else ""
    audio_enc = (
        f'ffmpeg -y -v error {offset} -i "{tmp_dir}/temp.mkv" '
        f'-c:a libopus -ac 2 -b:a 96k -map 0:a:0 -t {video_length} "{output}.AUDIO.mkv"'
    )
    print("Running command: " + audio_enc)
    os.system(audio_enc)

    kumannds = []

    kumannds.append(
        f'ffmpeg -y -v error -i "{output}.TEMP.mkv" -i "{output}.AUDIO.mkv" -map 0:v -map 1:a '
        f'-movflags +faststart -c:a copy -c:v copy "{output}"'
    )

    # second command that uses mkvmerge to write additional metadata & fixup the container
    # kumannds.append(f'mkvmerge -o "{output}" "{output}.TTEMP.mkv"')

    # remove temp
    kumannds.append(f'rm "{output}.TEMP.mkv"')
    kumannds.append(f'rm "{output}.AUDIO.mkv"')
    # kumannds.append(f'rm "{output}.TTEMP.mkv"')

    for command in kumannds:
        print("Running: " + command)
        os.system(command)
else:
    print("not muxing audio")
    argv_ = f'{get_binary("ffmpeg")} -v error -f concat -safe 0 -i mhmconcat -c copy "{output}"'
    print("Running: " + argv_)
    os.system(argv_)
    print("Removing mhmconcat")
    os.system("rm mhmconcat")
