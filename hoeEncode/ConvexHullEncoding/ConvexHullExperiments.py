import copy
import os
import time

from hoeEncode.ConvexHullEncoding.ConvexHull import ConvexEncoder, ConvexKummand
from hoeEncode.encode.ffmpeg.ChunkOffset import ChunkObject
from hoeEncode.encode.ffmpeg.FfmpegUtil import get_video_vmeth, EncoderJob, EncoderConfigObject
from hoeEncode.split.split import get_video_scene_list
from paraliezeMeHoe.ThaVaidioEncoda import gen_svt_kummands, run_kummand, CliKummand


def normal_svt(chank, crop_string, output, bitrate, two_pass):
    if os.path.exists(output):
        return []
    kommand = f'ffmpeg {chank.get_ss_ffmpeg_command_pair()} -c:v libsvtav1 {crop_string} -threads 1 ' \
              f'-g 999 -b:v {bitrate}'

    # Explainer
    # tune=0 - tune for PsychoVisual Optimization
    # scd=0 - disable scene change detection
    # enable-overlays=1 - enable additional overlay frame thing 😍
    # irefresh-type=1 - open gop
    # lp=1 - one thread
    svt_common_params = 'tune=0:scd=0:enable-overlays=1:irefresh-type=1:lp=1'

    # NOTE:
    # I use this svt_common_params thing cuz we don't need grain synth for the first pass + its faster

    kummands = []

    if two_pass:
        kommand += f" -passlogfile {output}svt"
        kummands.append(kommand + f' -svtav1-params {svt_common_params} -preset 7 -pass 1 '
                                  f'-pix_fmt yuv420p10le -an -f null /dev/null')
        kummands.append(kommand + f' -svtav1-params {svt_common_params}:film-grain=5 -preset 3 -pass 2'
                                  f' -pix_fmt yuv420p10le -an {output}')
    else:
        kummands.append(f'{kommand} -svtav1-params {svt_common_params}:film-grain=5'
                        f' -preset 3 -pix_fmt yuv420p10le -an {output}')
    return kummands


def sequence_test(scene_list, sequence_start, sequence_lenght=10, normal=False):
    temp_folder = './seq_test/'

    if normal:
        temp_folder = './seq_test_normal/'

    if not os.path.exists(temp_folder):
        os.mkdir(temp_folder)

    # new scene list
    new_scene_list = []
    if sequence_lenght != -1:
        for i in range(sequence_start, sequence_start + sequence_lenght):
            new_scene_list.append(scene_list[i])
    elif sequence_lenght == -1:
        new_scene_list = scene_list

    jobs = []
    for i, scene in enumerate(new_scene_list):
        jobs.append(EncoderJob(ChunkObject(
            path=input_file,
            first_frame_index=scene[0],
            last_frame_index=scene[1]
        ), i, f'{temp_folder}{i}.ivf'))

    config = EncoderConfigObject()
    config.temp_folder = temp_folder
    config.two_pass = True
    config.bitrate = "500k"

    if normal:
        from tqdm.contrib.concurrent import process_map

        a = []

        for job in jobs:
            cli = CliKummand()
            for bb in normal_svt(job.chunk, '', job.encoded_scene_path, config.bitrate, config.two_pass):
                cli.kummands.append(bb)
                print(bb)
            a.append(cli)

        process_map(run_kummand,
                    a,
                    max_workers=7,
                    chunksize=1,
                    desc='Encoding Normal',
                    unit="scene")
    else:
        from hoeEncode.ConvexHullEncoding.AutoGrain import get_best_avg_grainsynth
        config.grain_synth = get_best_avg_grainsynth(scenes=scene_list,
                                                     input_file=input_file,
                                                     random_pick=3,
                                                     cache_filename='grainsynthcache.json',
                                                     temp_folder=temp_folder)

        print("AutoGrainSynth: " + str(config.grain_synth))

        if config.grain_synth == -1:
            raise Exception("AutoGrainSynth failed")

        cvmands = [ConvexKummand(job, copy.deepcopy(config)) for job in jobs]

        from tqdm.contrib.concurrent import process_map

        process_map(run_kummand,
                    cvmands,
                    max_workers=5,
                    chunksize=1,
                    desc='Encoding ConvexHull',
                    unit="scene")


if __name__ == '__main__':
    import logging

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    print("Setting up test environment")

    input_file = '/mnt/sda1/shows/The Chilling Adventures of Sabrina/Season 1/[TorrentCouch.net].The.Chilling.Adventures.Of.Sabrina.S01E04.720p.WEBRip.x264.mp4'
    # input_file = '/home/kokoniara/Downloads/chx.mp4'

    # abolute scene cache path
    cache_path = './scenecache.json'
    cache_path = os.path.abspath(cache_path)
    scene_list = get_video_scene_list(input_file, cache_path, skip_check=True)

    sequence_lenght = 20
    sequence_start = 584

    sequence_test(scene_list, sequence_start, sequence_lenght, normal=True)
    # sequence_test(scene_list, 1750, -1, normal=False)

    quit()

if __name__ == "__main__":
    # set up logging
    import logging

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    print("Setting up test environment")

    if not os.path.exists("./test/"):
        os.mkdir("./test/")

    input_file = '/mnt/sda1/movies/Tetris (2023)/Tetris.2023.1080p.WEB.H264-NAISU[rarbg].mkv'

    scene_list = get_video_scene_list(input_file, 'scenecache.json', skip_check=True)

    scene = scene_list[1810]

    chunk = ChunkObject(
        path=input_file,
        first_frame_index=scene[0],
        last_frame_index=scene[1]
    )
    # os.system(create_chunk_ffmpeg_pipe_command_using_chunk(in_chunk=chunk)+ " | flatpak run io.mpv.Mpv -")
    # quit()

    target_bitrate = "1000k"

    logging.info("Doing a normal encode using " + target_bitrate)

    job = EncoderJob(chunk, 10, './test/chank.ivf')
    config = EncoderConfigObject()
    config.temp_folder = "./test/"
    config.two_pass = True
    config.bitrate = target_bitrate
    # cropdetect = do_cropdetect(chunk)
    # if cropdetect != '':
    #     config.crop_string = f'-vf "crop={cropdetect}"'
    #     print(f"Computed croppy floppy: {config.crop_string}")

    normal_start = time.time()
    gen_svt_kummands(job, config).run()

    normal_size = os.path.getsize(job.encoded_scene_path)
    normal_vmaf = get_video_vmeth(job.encoded_scene_path, chunk)
    logging.info(f"Normal encode size: {normal_size} VMAF: {normal_vmaf}")

    print("Normal encode took: " + str(time.time() - normal_start) + " seconds")

    convex_start = time.time()
    logging.info("testing convex hull on chunk: " + str(chunk))

    convex = ConvexEncoder(job, config)
    job.encoded_scene_path = "./test/chank_convex.ivf"
    # general test
    convex.run()

    print("Convex encode took: " + str(time.time() - convex_start) + " seconds")
