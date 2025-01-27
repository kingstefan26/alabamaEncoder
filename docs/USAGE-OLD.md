[TOP-LEVEL](../README.md)

## Usage

For local or Celery-based encoding, use:

```bash
alabamaEncoder [-h] [INPUT FILE] [OUTPUT FILE] [flags]
```

A full list of arguments is provided below.

### Arguments

| Argument                      | Type  | Default                                                                    | Description                                                                                                              |
|-------------------------------|-------|----------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------|
| -h, --help                    |       |                                                                            | Show help.                                                                                                               |
| --encode_audio                | flag  | True                                                                       | Mux and transcode audio into the output video.                                                                           |
| --audio_params                | str   | "-c:a libopus -ac 2 -b:v 96k -vbr on -lfe_mix_level 0.5 -mapping_family 1" | Audio parameters, e.g., `-c:v libopus -ac 6`.                                                                            |
| --celery                      | flag  | False                                                                      | Run encode on a Celery cluster.                                                                                          |
| --autocrop                    | flag  | False                                                                      | Automatically detect and crop black bars.                                                                                |
| --video_filters               | str   | ""                                                                         | Override ffmpeg video filter parameters, e.g., `-vf crop=...`.                                                           |
| --bitrate                     | int   | 2000                                                                       | Video bitrate, e.g., `--bitrate 1000` for 1000kb/s, or use `auto` for auto bitrate picking.                              |
| --vbr_perchunk_optimisation   | flag  | True                                                                       | Auto-adjust chunk VBR bitrate to hit SSIM target.                                                                        |
| --crf                         | int   | -1                                                                         | CRF value for CRF encode mode.                                                                                           |
| --encoder                     | str   | SVT_AV1                                                                    | Encoder to use. Possible options can be found with `alabamaEncode --help`.                                               |
| --grain                       | int   | -1                                                                         | Grain synthesis value, `-1` for auto, `-2` for auto per chunk.                                                           |
| --vmaf_target                 | float | 96                                                                         | Target VMAF/metric score.                                                                                                |
| --max_scene_length            | int   | 10                                                                         | Maximum scene length in seconds.                                                                                         |
| --crf_based_vmaf_targeting    | flag  | True                                                                       | Target VMAF by adjusting CRF and calculating score.                                                                      |
| --auto_crf                    | flag  | False                                                                      | Find a CRF that hits target VMAF, calculate a peak bitrate cap, and encode using CRF VBV.                                |
| --chunk_order                 | str   | sequential                                                                 | Encode order of scenes: `random`, `sequential`, `length_desc`, `length_asc`, `reverse`.                                  |
| --start_offset                | int   | -1                                                                         | Offset from the beginning of the video (in seconds).                                                                     |
| --end_offset                  | int   | -1                                                                         | Offset from the end of the video (in seconds).                                                                           |
| --generate_previews           | flag  | True                                                                       | Generate .avif previews for encoded file.                                                                                |
| --hdr                         | flag  | False                                                                      | If true, do auto HDR10. If false, tonemap (assuming the input is HDR).                                                   |
| --crop_string                 | str   | ""                                                                         | Crop string to use, e.g., `1920:1080:0:0`, `3840:1600:0:280`. Obtained using the `cropdetect` ffmpeg filter.             |
| --scale_string                | str   | ""                                                                         | Scale string to use, e.g., `1920:1080`, `1280:-2`, `1920:1080:force_original_aspect_ratio=decrease`.                     |
| --dry_run                     | flag  | False                                                                      | Don't do final encode; just return encode command. Note that analysis (like CRF VMAF) will still happen.                 |
| --title                       | str   | ""                                                                         | Title to use in the encode's metadata.                                                                                   |
| --encoder_flag_override       | str   | ""                                                                         | Override encoder flags, except output paths, pass, rate control (`--crf`, `--qp`), and speed (`--cpu_used`, `--preset`). |
| --encoder_speed_override      | int   | 4                                                                          | Speed/preset level to use; encoder dependent. 0 is the slowest.                                                          |
| --color-primaries             | str   | bt709                                                                      | HDR10 related metadata.                                                                                                  |
| --transfer-characteristics    | str   | bt709                                                                      | HDR10 related metadata.                                                                                                  |
| --matrix-coefficients         | str   | bt709                                                                      | HDR10 related metadata.                                                                                                  |
| --maximum_content_light_level | int   | 0                                                                          | HDR10 related metadata.                                                                                                  |
| --frame-average-light         | int   | 0                                                                          | HDR10 related metadata.                                                                                                  |
| --chroma-sample-position      | int   | 0                                                                          | HDR10 related metadata.                                                                                                  |
| --multiprocess_workers        | int   | -1                                                                         | When not using Celery, how many encode processes to run at once. `-1` for auto scale.                                    |
| --sub_file                    | str   | ""                                                                         | Subtitle file, e.g., `/home/user/subs.vvt`.                                                                              |
| --vmaf_phone_model            | flag  | False                                                                      | Use VMAF's phone model.                                                                                                  |
| --vmaf_4k_model               | flag  | False                                                                      | Use VMAF's UHD model.                                                                                                    |
| --auto_accept_autocrop        | flag  | False                                                                      | Automatically accept autocrop.                                                                                           |
| --resolution_preset           | str   | ""                                                                         | Preset for the scale filter. Possible choices: 4k, 1440p, 1080p, 768p, 720p, 540p, 480p, 360p.                           |
| --ssim-db_target              | float | 20                                                                         | When doing auto bitrate, target SSIM dB.                                                                                 |
