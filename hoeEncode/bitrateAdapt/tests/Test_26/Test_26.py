import os.path
import shutil
import time

from hoeEncode.bitrateAdapt.AutoGrain import AutoGrain
from hoeEncode.bitrateAdapt.tests.TestUtil import get_test_scenes, get_a_chunk, path_setup
from hoeEncode.encoders.EncoderConfig import EncoderConfigObject
from hoeEncode.encoders.EncoderJob import EncoderJob
from hoeEncode.encoders.encoderImpl.Svtenc import AbstractEncoderSvtenc
from hoeEncode.ffmpegUtil import get_video_ssim, get_video_vmeth, get_total_bitrate

if __name__ == '__main__':
    print('Test 26: experimenting with ssim based quality targeting')

    test_env = './tst/'
    shutil.rmtree(test_env, ignore_errors=True)
    path_setup(test_env)

    input_file = '/mnt/sda1/shows/MILF Manor/MILF.Manor.S01E01.MILF.Said.Knock.You.Out.1080p.AMZN.WEBRip.DDP2.0.x264-NTb[rarbg].mkv'
    print('Preparing scenes for test file and using one')
    scenes = get_test_scenes(input_file, '/hoeEncode/bitrateAdapt/milfmanorE1.json')

    chunk = get_a_chunk(158, scenes, input_file)

    db_target = 19
    # 22 dB = 16x
    # 20 dB = 10x
    # 18 dB = 4x
    # 16 dB = 2x
    # 14 dB = 1.5x
    # 12 dB = 1.25x
    # 10 dB = 1.1x
    # 8 dB  = 1.05x
    # 6 dB  = 1.025x
    # 4 dB  = 1.0125x
    # 2 dB  = 1.00625x
    # 0 dB  = 1.003125x

    db_targets = {
        'very much hd': 22,
        'recomended': 21,
        'csual': 19,
        'ok': 18,
    }

    # don't allow the bitrate modifier to go above 0.5/1.5, if we target 1000k/s its min 500 max 1500
    complexity_clamp_down = 0.8
    complexity_clamp_up = 0.35
    clamp_complexity = True

    for i, rate_test in enumerate([1000]):
        print(f'\n\nrate test {rate_test}')
        test_start = time.time()
        job = EncoderJob(chunk, 0, f'{test_env}test{i}.ivf')

        grain = AutoGrain(chunk=chunk, test_file_path=job.encoded_scene_path)

        ideal_grain = grain.get_ideal_grain_butteraugli()

        config = EncoderConfigObject(temp_folder=test_env, two_pass=False, bitrate=rate_test, speed=10,
                                     grain_synth=ideal_grain)

        enc = AbstractEncoderSvtenc()
        enc.eat_job_config(job, config)
        enc.bias_pct = 1
        enc.run()

        (ssim, ssim_db) = get_video_ssim(job.encoded_scene_path, chunk, get_db=True)

        miss_from_db_target = db_target - ssim_db

        # Calculate the ratio between the target ssim dB and the current ssim dB
        ratio = 10 ** ((db_target - ssim_db) / 10)

        # Clamp the ratio to the complexity clamp
        if clamp_complexity:
            ratio = max(min(ratio, 1 + complexity_clamp_up), 1 - complexity_clamp_down)

        # Interpolate the ideal encode rate using the ratio
        ideal_rate = rate_test * ratio
        ideal_rate = int(ideal_rate)

        test_end = time.time()

        print(f'encode rate: {rate_test}k/s')
        print(f'ssim dB: {ssim_db}, target ssim dB: {db_target}')
        print(f'miss from dB target: {miss_from_db_target}')
        print(f'ratio = 10 ** (dB_target - dB) / 10 = {ratio}')
        print(f'ideal rate: encode_rate * ratio = {ideal_rate:.2f}k/s')

        print(f'\npreforming encode with {ideal_rate:.2f}k/s')

        final_config = EncoderConfigObject(temp_folder=test_env, two_pass=True, speed=4, bitrate=ideal_rate,
                                           grain_synth=ideal_grain)
        final_job = EncoderJob(chunk, 0, f'{test_env}final{i}.ivf')

        enc.eat_job_config(final_job, final_config)
        final_encode_start = time.time()
        enc.run()
        final_vmaf = get_video_vmeth(final_job.encoded_scene_path, chunk, disable_enchancment_gain=True, uhd_model=True)
        final_bitrate = int(get_total_bitrate(final_job.encoded_scene_path) / 1000)
        final_size = os.path.getsize(final_job.encoded_scene_path)
        final_encode_end = time.time()

        print(
            f'final stats:'
            f' vmaf={final_vmaf} '
            f' time={int(final_encode_end - final_encode_start)}s '
            f' bitrate={final_bitrate}k'
            f' test_time={int(test_end - test_start)}s'
        )

        # control_start = time.time()
        # print(f'\ndoing a control encode with the rate test bitrate {rate_test}')
        # final_config = EncoderConfigObject(temp_folder=test_env, two_pass=True, speed=3, bitrate=rate_test)
        # final_job = EncoderJob(chunk, 0, f'{test_env}final_control{i}.ivf')
        # enc.eat_job_config(final_job, final_config)
        # enc.run()
        # control_vmaf = get_video_vmeth(final_job.encoded_scene_path, chunk, disable_enchancment_gain=True,
        #                                uhd_model=True)
        # control_bitrate = int(get_total_bitrate(final_job.encoded_scene_path) / 1000)
        # control_size = os.path.getsize(final_job.encoded_scene_path)
        # control_end = time.time()
        #
        # print(f'control stats:'
        #       f' vmaf={final_vmaf}'
        #       f' time={int(control_end - control_start)}s'
        #       f' bitrate={control_bitrate}k')
        #
        # reduction = (control_size - final_size) / control_size * 100
        #
        # reduction = reduction * -1
        #
        # vmaf_improvement = (final_vmaf - control_vmaf) / control_vmaf * 100
        #
        # print(f'\nFile size difference compared to control: {reduction:.2f}%')
        # print(f'VMAF change to control: {vmaf_improvement:.2f}%')
        #
        # time_reduction = (((final_encode_end - final_encode_start) + (test_end - test_start)) - (
        #             control_end - control_start)) / (control_end - control_start) * 100
        # print(f'Time difference compared to control: {time_reduction:.2f}% ')
