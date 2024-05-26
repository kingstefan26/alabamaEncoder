Here's a polished version of the README.md for the `alabamaEncoder` video encoding framework:

---

# AlabamaEncoder

AlabamaEncoder is a powerful video encoding framework designed for macOS & Linux. It is able to leverage multi-PC setups, and currently supports various encoders such as [SVT-AV1](https://wiki.x266.mov/docs/encoders/SVT-AV1), [aomenc](https://wiki.x266.mov/docs/encoders/aomenc), [rav1e](https://wiki.x266.mov/docs/encoders/rav1e), [x265](https://wiki.x266.mov/docs/encoders/x265), and [x264](https://wiki.x266.mov/docs/encoders/x264), among others.

*Note: this utility is a work in progress. It may not function as expected. Please report any issues you encounter.*

## Installation

1. First, clone the upstream GitHub repository:

```bash
git clone https://github.com/kingstefan26/alabamaEncoder
```

2. Next, set up the Python virtual environment:

```bash
python -m venv venv
source venv/bin/activate
```

*Note: make sure to use `venv/bin/activate.fish` if you use the fish shell*

3. Finally, install the required dependencies:

```bash
pip install -r requirements.txt
```

From here, you can either run the program without building it, or build & install it.

**Run Without Building**

```bash
python -m alabamaEncode_frontends.cli <cli_args>
```

**Build & Install**

To build and install the local version:

```bash
pip install build
python -m build
pipx install . --editable --force
```

**Install with `pipx`**

To install AlabamaEncoder with pipx:

```bash
pipx install alabamaEncoder
```

Ensure `SvtAv1EncApp`, `ffmpeg`, `ffprobe`, and any other encoder binaries you wish to use are available in your PATH. The program will notify you if any dependencies are missing.

## Command-Line Interface (CLI)

For local or Celery-based encoding, use:

```bash
alabamaEncoder [-h] [INPUT FILE] [OUTPUT FILE] [flags]
```

For a more comprehensive breakdown of the arguments and flags, see our [USAGE page](./docs/USAGE.md).

### Non-Mainline Encoders

To use one of the many community-built forks of mainline video encoders (like [SVT-AV1-PSY](https://github.com/gianni-rosato/svt-av1-psy)), you may do the following:

- Get the path of the binary.
- Set it in an environment variable following this pattern: `<CLI_NAME_ALL_UPPER_CASE>_CLI_PATH`.

Example:

```bash
export SVTAV1ENCAPP_CLI_PATH=/path/to/SvtAv1EncApp # Custom path
alabamaEncoder [arguments...]
```

This applies to *all* binaries used by AlabamaEncoder. So, to use a custom build of ffmpeg, set the `FFMPEG_CLI_PATH` environment variable.

### Multi-System Encoding

#### Setup

- Ensure all paths on all PCs are the same. This can be achieved by encoding on an NFS share mounted on the same path everywhere.
- You will need a job broker for Celery. The simplest option is Redis. Run the following:

```bash
docker run -d -p 6379:6379 --rm redis
```

Set the Redis host environment variable for both workers and the main command:

```bash
export REDIS_HOST=192.168.1.10
alabamaEncoder worker 10
```

By default, the Redis host is assumed to be `localhost`.

To clear the Celery job queue:

```bash
alabamaEncoder clear
```

### Notes

- Bandwidth overhead is low with smart FFmpeg seeking. A 1 Gb/s LAN is sufficient.
- Content analysis/scene detection is done on the system running the main command. This will ideally be configurable in the future, but is not at this time.

### Examples

Here's an example of an Adaptive encoding command for alabamaEncoder:

```bash
alabamaEncoder input.mkv output-av1.webm --autocrop --resolution_preset 1080p --grain -2 --hdr --audio_params "-c:a libopus -b:a 170k -ac 6 -mapping_family 1" --vmaf_target 95 --end_offset 60 --start_offset 60 --title "TV SHOW (2023) S00E00"
```

Now, let's break down what this command is doing:

- `alabamaEncoder input.mkv output-av1.webm`

Specifies that alabamaEncoder should encode `./input.mkv` to `./output-av1.webm`

- `--autocrop`

Crops black bars

- `--resolution_preset 1080p`

Downscales to a 1080p resolution

- `--grain -2`

Automatically adjusts film grain synthesis on a per-scene basis

- `--hdr`

Preserves HDR metadata resulting in a proper HDR output

- `--audio_params "-c:a libopus -b:a 170k -ac 6 -mapping_family 1"`

Transcodes audio to 170k 5.1 Opus

- `--vmaf_target 95`

Uses ideal CRF to achieve a VMAF score of 95 on a per-scene basis

- `--end_offset 60 --start_offset 60`

Cuts the first and last minute.

- `--title "TV SHOW (2023) S00E00"`

Adds metadata title.

- `[no encoder specified]`

Encodes using SvtAv1EncApp by default when an encoder is not specified.

---

Here's an example of a Constant Rate Factor encoding command for alabamaEncoder:

```bash
alabamaEncoder /path/to/movie.m

kv ./dir/out.webm --audio_params "-c:a libopus -b:a 256k -ac 8 -mapping_family 1" --grain 17 --scale_string="1920:-2" --crf 24 --encoder aomenc
```

This command:
- Downscales `movie.mkv` to a 1080p resolution.
- Tonemaps if HDR.
- Uses 7.1 256kb/s Opus audio.
- Encodes with aomenc using grain denoise at level 17, speed 4, CRF 25.
- Muxes and encodes audio with the specified ffmpeg parameters.

## Notes

- If `alabamaEncoder` is already running, you can spin up new workers (multi-PC guide), and they will automatically connect and split the workload.
- If you crash or abort the script, rerun it with the same arguments, and it will pick up where it left off.
- Extensive testing has been done to ensure frame-perfect ffmpeg-based split/concat methods. However, if you encounter any issues, please create an issue and provide a sample.
- All feedback is welcome. Create an issue for explanations, bug fixes, or feature requests.

## Credits

Thanks to all contributors and developers of the tools used in this project.
