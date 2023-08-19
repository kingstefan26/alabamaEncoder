# My vadeio encoda

this is my attempt at encoding in a multi pc setup, currently supports svtav1

![lovely screenshot of the worker](Screenshotidfk.png)

## **WARNING: THIS IS A WORK IN PROGRESS, IT MAY NOT WORK, IT MAY EAT YOUR FILES, IT MAY EAT YOUR PC

# Installation

* pull this repo
* `pip install -r requirements.txt`
* `python setup.py bdist_wheel`
* `pip install --force-reinstall dist/video_encoder-0.1-py3-none-any.whl`
* For basic usage make sure `SvtAv1EncApp`/`ffmpeg`/`ffprobe` are available on your path (you can use them in cli),
  otherwise the program will crash if something is missing
* enjoy

# CLI

if running celery the celery broker ip should be under `REDIS_HOST` env var,
eg `REDIS_HOST=192.168.1.10 alabamaEncoder worker 10`  
otherwise assumed to be `localhost`

for workers:

````
alabamaEncoder worker [# of worker processes] 
````

for general:

````
alabamaEncoder [-h] [INPUT] [OUTPUT] [TEMP DIR PATH] [flags from bellow]
````

To clear the celery queue: `alabamaEncoder clear`

| argument                | type  | description                                                                                                             |
|-------------------------|-------|-------------------------------------------------------------------------------------------------------------------------|
| -h, --help              |       | show help                                                                                                               |
| --audio                 | flag  | mux+transcode audio into the final video                                                                                |
| --audio_params          | str   | params for audio, eg `-c:v libopus -ac 6`                                                                               |
| --celery                | flag  | run encode on celery cluster                                                                                            |
| --video_filters         | str   | override ffmpeg vf params, put your `-vf crop=...` or even a filter_graph, mutually exclusive with scale & crop strings |
| --bitrate               | int   | video bitrate, eg `--bitrate 1000` for 1000kb/s, use `auto` for auto bitrate picking                                    |
| --bitrate_adjust        | flag  | Ajust the bitrate per chunks, or run every chunk under vbr at specified bitrate                                         |
| --multiprocess_workers  | int   | when not using celery, how many encode processes to run at once, `-1` for auto scale                                    |
| --ssim-db-target        | float | when doing autobirate what ssim dB should the bitrate target                                                            |
| --grain                 | int   | SvtAv1 grain synth value, `-1` for auto, you need `butteraguli` in order to use it                                      |
| --autoparam             | flag  | automatically set some parameters based on the input video                                                              |
| --vmaf_target           | float | what vmaf to target with auto ladder, default 96                                                                        |
| --max_scene_length      | int   | dont allow scenes longer than this, in seconds                                                                          |
| --chunk_order           | str   | Encode order of scenes: `random`, `sequential`, `length_desc`, `length_asc`, `sequential_reverse`                       |
| --start_offset          | int   | Offset from the beginning of the video (in seconds), useful for cutting intros etc                                      |
| --end_offset            | int   | Offset from the end of the video (in seconds), useful for cutting end credits outtros etc                               |
| --generate_previews     | flag  | Generate .avif previews for encoded file                                                                                |
| --hdr                   | flag  | Encode in HDR, if off and input is HDR, if not there it will be tonemapped to SDR (HDR encoding currently not working)  |
| --crop_string           | str   | Crop string to use, eg `1920:1080:0:0`, `3840:1600:0:280`. Obtained using the `cropdetect` ffmpeg filter                |
| --scale_string          | str   | Scale string to use, eg. `1920:1080`, `1280:-2`, `1920:1080:force_original_aspect_ratio=decrease`                       |
| --title                 | str   | Title to use in encode's metadata                                                                                       |
| --encoder_flag_override | str   | Override encoder flags by the program, put everything here except output paths & pass commands                          |

### Multi System Encoding

#### to encode multi-system, you need to:

- make sure all the paths on all the pcs are the same, easily done by encoding on a nfs share that's on mounted on the
  same path everywhere
- The easiest broker for celery is redis a simple `docker run -d -p 6379:6379 --rm redis`, then set the env variable
  from above

#### Things to Note:

- Since i use ffmpeg seeking the bandwidth overhead is low
- the content analysis/scene detection is done on the system that's running the main command, will be configurable in
  the future

### Examples:

#### adaptive encoding;

````
alabamaEncoder /mnt/data/Tv_Show.S01E01/Tv_Show.S01E01.2160p.mkv ~/dir/Tv_Show.S01E01.AV1.1080p.webm ~/dir/ --audio --bitrate 1000 --autoparam --video_filters crop=3840:1600:0:280,scale=1920:-2:flags=lanczos --grain 5 --audio_params "-c:a libopus -b:a 170k -ac 6 -lfe_mix_level 0.5 -mapping_family 1" --end_offset 60 --start_offset 60 --title "TV SHOW (2023) S01E01"
````

this will downscale /mnt/data/Tv_Show.S01E01/Tv_Show.S01E01.2160p.mkv to 1080p width video, crop the black bars,
transcode audio to 170k 5.1 opus, cut the first and last minute, add a metadata title, use 1000kb/s bitrate that will be
adjusted per chunk, and use SvtAv1 grain synth with a strength of 5

#### constant quality encoding using aomenc

````
alabamaEncoder /path/to/movie.mkv  ./dir/out.webm ./dir/ --audio --audio_params "-c:a libopus -b:a 256k -ac 8 -lfe_mix_level 0.5 -mapping_family 1"  --grain 17 --scale_string="1920:-2" --crf 24 --encoder aomenc
````

Downscale movie.mkv to a 1080p class resolution, tonemap if hdr,
then use aomenc to encode with grain denoise at level 17, speed 4, finally mux and encode audio with above ffmpeg params

## Notes

- To run your encode with fully custom commands, do `--crf whatever` and put your flags in `--encoder_flag_override`,
  using --crf will stop any content analysis expect scene spliting
- if you already are running `alabamaEncoder`, you can spin up new workers (multi pc guide), they will automatically
  connect
  and split the workload
- if you crash/abort the script, dont worry, just rerun it with the same arguments and it will pick up where it left
  off
- i *personally* did lots of testing and my ffmpeg split/concat method is frame perfect, but if you find any issues,
  please provide a sample and create a issue

## TODO

- [ ] make the docker image smaller (its 4gb lmao)
- [X] add support for more encoders (easy but idrc)
- [X] split the ThaVaidioEncoda.py into multiple files
- [X] Auto muxing & auto encoding
- [X] Auto retry failed chunks & auto merge
- [X] add cli interface to main.py
- [X] dynamically select worker_concurrency based on load average
- [ ] alternative to nfs file for worker sharing
- [X] fix non ideal scene splits, improve scene detection/keyframe placement

### far future

- [X] auto bitrate_lader_selection/convex_hull_enocding for extra ~10% efficiency
- [X] auto grain synthesis (50% done, needs more testing)
- [X] auto param tuner

# general design

### vertical scaling

For a long time, encoders were simple enough that more cpu = faster, then av1 came. the encoding process contained so
many dependencies that more threads just didn't help the speed after a certain point.
ofc encoders like SvtAv1 can pin all threads but that's only on high presets, we eventually run into a wall where we
have some dependencies and cant parallelize the encoding more.
So we had to start thinking about "horizontal scaling"

### encoding and horizontal scaling

video encoding doesn't scale horizontally, that's why splitting the video into chunks and encoding each chunk
independently is popular,

### why not just split the video into chunks and encode them in parallel

Just spliting the video every, lets say 4s seconds might result in bad keyframe placment tho. Since one shot contains a
lot of temporal redundancy and just putting a I frame in the middle of a long shot is wasted space.

### Shot-based splitting

Thats why projects like av1an/this/Netflix'es encoding pipeline split the video based on shots so we can put a single I
frame at the begging and save a lot of space. Think a long zoom out shot, the frames look almost the same for multiple
seconds aka free gains. Also, allowing us to use open gop

### Why not just use Av1an

- Well first of all it was rewritten in rust, and while rust great n all: 1. I don't rust lmao 2. You don't need a
  memory safe, compiled language to execute some shell commands in order... get real
- It uses vapoursynth, which is a great, but for some reason it doesn't work on my pc (i tried)
- It only works on a single pc, so the advantage of infinite horizontal scaling possible by splitting is constrained to
  only one system

## Credits

all the people i stole code from, and the people who made the tools i used