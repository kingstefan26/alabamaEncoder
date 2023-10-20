"""
Testing enable-tf=0 In SvtAv1
"""
import json

import pandas as pd

from alabamaEncode.encoders.encoder.impl.Svtenc import AbstractEncoderSvtenc
from alabamaEncode.experiments.util.ExperimentUtil import (
    get_test_env,
    run_tests_across_range,
)


def run_test():
    test_env = get_test_env()
    # test_env = "/home/kokoniara/dev/VideoSplit/alabamaEncode/experiments/util/run_2023-10-18_23-24-55/"
    experiment_name = (
        "Testing ALT-REF (temporally filtered) frames --enable-tf, speed 4"
    )
    encControl = AbstractEncoderSvtenc()
    encControl.update(speed=4)
    encControl.svt_tune = 1
    encControl.threads = 12

    encTest = AbstractEncoderSvtenc()
    encTest.svt_tf = 0
    encTest.svt_tune = 1
    encTest.update(speed=4)
    encTest.threads = 12

    run_tests_across_range(
        [encControl, encTest], title=experiment_name, test_env=test_env
    )

def analyse():
    path1 = "/home/kokoniara/dev/VideoSplit/alabamaEncode/experiments/util/run_2023-10-19_16-34-48/Testing ALT-REF (temporally filtered) frames --enable-tf, speed 4 Bitrates.json"

    with open(path1) as f:
        data = json.load(f)

    # only get  size bitrate vmaf ssim vmaf_percentile_1 vmaf_percentile_5 vmaf_percentile_10 vmaf_percentile_25 vmaf_percentile_50 vmaf_avg basename version
    for i in range(len(data)):
        data[i] = {
            k: data[i][k]
            for k in (
                "size",
                "bitrate",
                "vmaf",
                "ssim",
                "vmaf_percentile_1",
                "vmaf_percentile_5",
                "vmaf_percentile_10",
                "vmaf_percentile_25",
                "vmaf_percentile_50",
                "vmaf_avg",
                "basename",
                "version",
            )
        }

    # print(data[0])

    # turn to dataframe
    df = pd.DataFrame(data)
    print(df)

    def g(df):
        df["rate"] = (
            df["version"]
            .str.split("_")
            .str[-1]
            .str.replace("crf", "")
            .str.replace("kbs", "")
            .astype(int)
        )
        df["test_group"] = df["version"].str.split("_").str[0]
        return df

    df = g(df.copy())


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
    print(f"overall VMAF 1%tile avg: {sum(vmaf1percenttile_change_arr) / len(vmaf1percenttile_change_arr)}%")
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
        plt.savefig("/home/kokoniara/dev/VideoSplit/alabamaEncode/experiments/util/run_2023-10-19_16-34-48/" + key + ".png")


if __name__ == '__main__':
    # run_test()
    pass