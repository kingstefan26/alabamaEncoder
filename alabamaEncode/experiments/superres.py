"""
Testing svtav1 --superres-mode 4

from svtav1 gitlab:

SuperresMode
--superres-mode [0-4] 0
Enable super-resolution mode, refer to the super-resolution section below for more info


SuperresDenom
--superres-denom [8-16] 8
Super-resolution denominator, only applicable for mode == 1 [8: no scaling, 16: half-scaling]


SuperresKfDenom
--superres-kf-denom [8-16] 8
Super-resolution denominator for key frames, only applicable for mode == 1 [8: no scaling, 16: half-scaling]


SuperresQthres
--superres-qthres [0-63] 43
Super-resolution q-threshold, only applicable for mode == 3


SuperresKfQthres
--superres-kf-qthres
[0-63]
43
Super-resolution q-threshold for key frames, only applicable for mode == 3

Super-Resolution

Super resolution is better described in the Super-Resolution documentation,
but this basically allows the input to be encoded at a lower resolution,
horizontally, but then later upscaled back to the original resolution by the
decoder.

SuperresMode

0 None, no frame super-resolution allowed
1 All frames are encoded at the specified scale of 8/denom, thus a denom of 8 means no scaling, and 16 means half-scaling
2 All frames are coded at a random scale
3 Super-resolution scale for a frame is determined based on the q_index, a qthreshold of 63 means no scaling
4 Automatically select the super-resolution mode for appropriate frames

The performance of the encoder will be affected for all modes other than mode
0. And for mode 4, it should be noted that the encoder will run at least twice,
one for down scaling, and another with no scaling, and then it will choose the
best one for each of the appropriate frames.
For more information on the decision-making process,
please look at section 2.2 of the super-resolution doc

"""
import os
from copy import deepcopy

from alabamaEncode.encoder.impl.Svtenc import EncoderSvt
from alabamaEncode.experiments.util.ExperimentUtil import (
    run_tests_across_range,
    read_report,
)

experiment_name = "Testing SvtAv1 SUPERRES, speed 6"

test_env = os.getcwd() + "/data/superres/"
if not os.path.exists(test_env):
    os.makedirs(test_env)

report_path = test_env + experiment_name + " CRF.json"


def analyze():
    df = read_report(report_path)

    print(df)

    enc1_vmaf1percenttile_change_arr = []
    enc1_size_change_arr = []
    enc1_vmaf_change_arr = []
    enc1_ssim_change_arr = []
    enc1_bpv_change_arr = []

    enc2_vmaf1percenttile_change_arr = []
    enc2_size_change_arr = []
    enc2_vmaf_change_arr = []
    enc2_ssim_change_arr = []
    enc2_bpv_change_arr = []

    for key, group in df.groupby("basename"):
        print(key)
        control = 0
        enc1 = 0
        for key_j, group_j in group.groupby("test_group"):
            print(key_j)
            # avg 1%tile vmaf
            score = group_j["vmaf_percentile_1"].mean()
            size_score = group_j["size"].mean()
            vmaf_score = group_j["vmaf"].mean()
            ssim_score = group_j["ssim"].mean()

            # how much bits per vmaf
            bpv_score = group_j["size"].mean() / group_j["vmaf"].mean()

            if key_j == "control":
                control = score
                size_control = size_score
                vmaf_control = vmaf_score
                ssim_control = ssim_score
                bpv_control = bpv_score
            elif key_j == "enc1":
                enc1 = score
                size_enc1 = size_score
                vmaf_enc1 = vmaf_score
                ssim_enc1 = ssim_score
                bpv_enc1 = bpv_score
            elif key_j == "enc2":
                enc2 = score
                size_enc2 = size_score
                vmaf_enc2 = vmaf_score
                ssim_enc2 = ssim_score
                bpv_enc2 = bpv_score

        # show pct of difference between control and enc1

        enc1_vmaf1percenttile_change_arr.append((enc1 - control) / control * 100)
        enc1_size_change_arr.append((size_enc1 - size_control) / size_control * 100)
        enc1_vmaf_change_arr.append((vmaf_enc1 - vmaf_control) / vmaf_control * 100)
        enc1_ssim_change_arr.append((ssim_enc1 - ssim_control) / ssim_control * 100)
        enc1_bpv_change_arr.append((bpv_enc1 - bpv_control) / bpv_control * 100)

        enc2_vmaf1percenttile_change_arr.append((enc2 - control) / control * 100)
        enc2_size_change_arr.append((size_enc2 - size_control) / size_control * 100)
        enc2_vmaf_change_arr.append((vmaf_enc2 - vmaf_control) / vmaf_control * 100)
        enc2_ssim_change_arr.append((ssim_enc2 - ssim_control) / ssim_control * 100)
        enc2_bpv_change_arr.append((bpv_enc2 - bpv_control) / bpv_control * 100)

    print(f"enable-overlays.md=1 tests")
    print("ENC1 (SUPERRES MODE 4)")
    print(
        f"overall VMAF 1%tile avg (positive mean better): {sum(enc1_vmaf1percenttile_change_arr) / len(enc1_vmaf1percenttile_change_arr)}%"
    )
    print(
        f"overall size avg (positive mean worse): {sum(enc1_size_change_arr) / len(enc1_size_change_arr)}%"
    )
    print(
        f"overall VMAF avg (positive mean better): {sum(enc1_vmaf_change_arr) / len(enc1_vmaf_change_arr)}%"
    )
    print(
        f"overall SSIM avg (positive mean better): {sum(enc1_ssim_change_arr) / len(enc1_ssim_change_arr)}%"
    )
    print(
        f"overall Bits Per vmaf avg (positive mean worse): {sum(enc1_bpv_change_arr) / len(enc1_bpv_change_arr)}%"
    )

    print("\nENC2 (SUPERRES MODE 3 WITH DEFAULTS)")
    print(
        f"overall VMAF 1%tile avg (positive mean better): {sum(enc2_vmaf1percenttile_change_arr) / len(enc2_vmaf1percenttile_change_arr)}%"
    )
    print(
        f"overall size avg (positive mean worse): {sum(enc2_size_change_arr) / len(enc2_size_change_arr)}%"
    )
    print(
        f"overall VMAF avg (positive mean better): {sum(enc2_vmaf_change_arr) / len(enc2_vmaf_change_arr)}%"
    )
    print(
        f"overall SSIM avg (positive mean better): {sum(enc2_ssim_change_arr) / len(enc2_ssim_change_arr)}%"
    )
    print(
        f"overall Bits Per vmaf avg (positive mean worse): {sum(enc2_bpv_change_arr) / len(enc2_bpv_change_arr)}%"
    )


def test():
    control = EncoderSvt()
    control.speed = 6
    control.threads = 12
    control.svt_tune = 1

    enc_test = deepcopy(control)
    enc_test.svt_supperres_mode = 4

    enc_test2 = deepcopy(control)
    enc_test2.svt_supperres_mode = 3

    run_tests_across_range(
        [control, enc_test, enc_test2],
        title=experiment_name,
        test_env=test_env,
        skip_vbr=True,
    )


if __name__ == "__main__":
    # test()
    analyze()
    pass
