"""
Testing enable-tf=0 In SvtAv1
"""
import os
from copy import deepcopy

from alabamaEncode.encoder.impl.Svtenc import EncoderSvt
from alabamaEncode.experiments.util.ExperimentUtil import (
    run_tests_across_range,
    read_report,
)

experiment_name = "Testing ALT-REF (temporally filtered) frames --enable-tf, speed 4"

test_env = os.getcwd() + "/data/temporal_filtering/"
if not os.path.exists(test_env):
    os.makedirs(test_env)

report_path = test_env + experiment_name + " CRF.json"


def run_test():
    control = EncoderSvt()
    control.speed = 4
    control.threads = 12
    control.svt_tune = 1
    control.svt_tf = 1

    enc_test = deepcopy(control)
    enc_test.svt_tf = 0

    run_tests_across_range(
        [control, enc_test],
        title=experiment_name,
        test_env=test_env,
        skip_vbr=True,
    )


def analyse():
    df = read_report(report_path)
    print(df)

    vmaf1percenttile_change_arr = []
    size_change_arr = []
    vmaf_change_arr = []
    ssim_change_arr = []

    for key, group in df.groupby("basename"):
        print(key)
        control = 0
        enc1 = 0
        for key_j, group_j in group.groupby("test_group"):
            print("")
            # avg 1%tile vmaf
            score = group_j["vmaf_percentile_1"].mean()
            size_score = group_j["size"].mean()
            vmaf_score = group_j["vmaf"].mean()
            ssim_score = group_j["ssim"].mean()
            if key_j == "control":
                control = score
                size_control = size_score
                vmaf_control = vmaf_score
                ssim_control = ssim_score
            else:
                enc1 = score
                size_enc1 = size_score
                vmaf_enc1 = vmaf_score
                ssim_enc1 = ssim_score

        # show pct of difference between control and enc1

        vmaf1percenttile_change_arr.append((enc1 - control) / control * 100)
        size_change_arr.append((size_enc1 - size_control) / size_control * 100)
        vmaf_change_arr.append((vmaf_enc1 - vmaf_control) / vmaf_control * 100)
        ssim_change_arr.append((ssim_enc1 - ssim_control) / ssim_control * 100)

    print(f"positive means enable-tf=0 is better")
    print(
        f"overall VMAF 1%tile avg: {sum(vmaf1percenttile_change_arr) / len(vmaf1percenttile_change_arr)}%"
    )
    print(f"overall size avg: {sum(size_change_arr) / len(size_change_arr)}%")
    print(f"overall VMAF avg: {sum(vmaf_change_arr) / len(vmaf_change_arr)}%")
    print(f"overall SSIM avg: {sum(ssim_change_arr) / len(ssim_change_arr)}%")

    quit()

    # split into separate df based on basename
    for key, group in df.groupby("basename"):
        print(key)
        fig, ax = plt.subplots()
        for key_j, group_j in group.groupby("test_group"):
            group_j.plot(
                ax=ax,
                kind="scatter",
                x="size",
                y="vmaf_percentile_1",
                label=key_j,
                color=("red" if key_j == "control" else "blue"),
            )

        # 3d plot rate vmaf_percentile_1 size colored by test_group
        # fig = plt.figure()
        # ax = fig.add_subplot(111, projection="3d")
        # for key_j, group_j in group.groupby("test_group"):
        #     ax.scatter(
        #         group_j["rate"],
        #         group_j["vmaf_percentile_1"],
        #         group_j["size"],
        #         label=key_j,
        #         color=("red" if key_j == "control" else "blue"),
        #     )
        # ax.set_xlabel("rate")
        # ax.set_ylabel("vmaf_percentile_1")
        # ax.set_zlabel("size")

        plt.title(key)
        plt.savefig(test_env + key + ".png")


if __name__ == "__main__":
    run_test()
    pass
