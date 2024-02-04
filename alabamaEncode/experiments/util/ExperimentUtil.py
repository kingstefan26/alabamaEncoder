import json
import os
from datetime import datetime
from typing import List

import pandas as pd
from pandas import DataFrame
from tqdm import tqdm

from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution
from alabamaEncode.encoder.stats import EncodeStats
from alabamaEncode.metrics.impl.vmaf import VmafOptions
from alabamaEncode.metrics.metric import Metric
from alabamaEncode.scene.chunk import ChunkObject

only_one = False


def get_test_files(test_files_count: int = -1):
    # get test_files env
    test_files = os.environ.get("TEST_FILES")
    if test_files is None:
        test_files = "/mnt/data/objective-1-fast"

    # get all files in dir
    files = []
    for root, dirs, filenames in os.walk(test_files):
        for f in filenames:
            files.append(os.path.join(root, f))

    # filter out non y4m
    files = [f for f in files if f.endswith(".y4m")]

    if test_files_count != -1:
        # limit so no less than zero and no more than the number of files is picked
        test_files_count = max(min(test_files_count, len(files)), 0)
        files = files[:test_files_count]

    return files


def get_test_env() -> str:
    pwd = os.getcwd()
    date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    test_env = pwd + f"/run_{date}/"
    # if not os.path.exists(test_env):
    #     os.mkdir(test_env)

    return test_env


def run_test(
    enc: Encoder, input_file: str, version: str, test_env: str = get_test_env()
) -> EncodeStats:
    # get the basename of the file
    basename = os.path.basename(input_file).split(".")[0]

    # create and set an output input_path for the video file
    # eg ./encode_test_2021-03-30_16-00-00/STARCRAFT_60f_420control.ivf
    output_path = f"{test_env}{basename}_{version}{enc.get_chunk_file_extension()}"

    threads = os.cpu_count()

    # set the input and output input_path
    enc.chunk = ChunkObject(path=input_file)
    enc.output_path = output_path
    enc.threads = threads
    stats = enc.run(
        override_if_exists=False,
        metric_to_calculate=Metric.VMAF,
        calcualte_ssim=True,
        metric_params=VmafOptions(neg=True, threads=threads),
    )
    stats.version = version
    stats.basename = basename
    return stats


def run_tests(
    enc: Encoder,
    version: str = "control",
    test_env: str = get_test_env(),
    test_files_count: int = -1,
) -> List[EncodeStats]:
    """
    Run a test on all the files in the TEST_FILES env
    :param test_env: where to save the encoded files
    :param enc: Configured encoder object to run the test with
    :param version: version name to attach to the stats, e.g., "control"
    :return: a list of EncodeStats objects
    """
    test_files = get_test_files(test_files_count)

    stat_reports = []

    for input_path in tqdm(test_files, desc=f"Running tests for {version}", leave=None):
        stat_reports.append(
            run_test(enc, input_file=input_path, version=version, test_env=test_env)
        )

    return stat_reports


def save_stats(
    stat_reports: List[EncodeStats],
    experiment_name: str = "Experiment",
    test_env: str = get_test_env(),
):
    """
    Save the stats to a json file
    :param test_env: where to save the encoded files
    :param stat_reports: a list of EncodeStats objects
    :param experiment_name: name of the experiment
    :return: None
    """
    # save the stats to a json file
    output_path = f"{test_env}{experiment_name}.json"
    if os.path.exists(output_path):
        print(f"WARNING: {output_path} already exists, overwriting")
    with open(output_path, "w") as f:
        # save as a list of dicts
        json.dump([s.get_dict() for s in stat_reports], f)


def report(stat_reports: List[EncodeStats], experiment_name: str = "Experiment"):
    print(f"## {experiment_name}")

    class StatHolder:
        def __init__(
            self, basename, sts: List[EncodeStats], control: EncodeStats = None
        ):
            self.basename = basename
            self.sts = sts
            self.control = control

    holders = []

    # put stats with the same basename together in StatHolder, also put control in the holder
    for stat in stat_reports:
        if stat is None:
            raise ValueError("stat is None")
        found = False
        for s in holders:
            if s.basename == stat.basename:
                if stat.version == "control":
                    s.control = stat
                else:
                    s.sts.append(stat)
                found = True
                break
        if not found:
            if stat.version == "control":
                holders.append(StatHolder(stat.basename, [], stat))
            else:
                holders.append(StatHolder(stat.basename, [stat]))

    # print the stats
    for holder in holders:
        print(
            f"| _{holder.basename}_ |  time taken  | kpbs | vmaf  | BD Change % | time Change % | performance |\n"
            "|----------|:------:|:----:|:-----:|:-----------:|:---:|:---:|"
        )

        control = EncodeStats() if holder.control is None else holder.control

        # since we will sometimes be having multiple controls and dont set the control object, we have a fallback
        # to just print them
        stat_to_process = [*holder.sts, holder.control]

        if holder.control is None:
            stat_to_process = holder.sts

        for stat in stat_to_process:
            stat.time_encoding = round(stat.time_encoding, 2)
            curr_db_rate = stat.bitrate / stat.vmaf

            if control.bitrate == -1 or control.vmaf == -1:
                db_change_from_control = 0
            else:
                db_change_from_control = (
                    (curr_db_rate - control.bitrate / control.vmaf)
                    / (control.bitrate / control.vmaf)
                    * 100
                )
                db_change_from_control = round(db_change_from_control, 2)

            if control.time_encoding == -1:
                time_change_from_control = 0
            else:
                time_change_from_control = (
                    0
                    if control.time_encoding == -1
                    else (
                        (stat.time_encoding - control.time_encoding)
                        / control.time_encoding
                        * 100
                    )
                )
                time_change_from_control = round(time_change_from_control, 2)

            preformance = (stat.vmaf / stat.time_encoding / stat.bitrate) * 1000

            print(
                f"| {stat.version} |"
                f" {stat.time_encoding}s |"
                f" {stat.bitrate} "
                f"| {round(stat.vmaf, 2)} | "
                f" {db_change_from_control}% |"
                f" {time_change_from_control}% |"
                f" {round(preformance, 2)} |"
            )


def run_tests_across_range(
    encs: List[Encoder],
    title: str,
    test_env: str = get_test_env(),
    crfs: List[int] = [
        16,
        20,
        24,
        28,
        33,
        39,
        48,
        51,
        57,
        60,
    ],
    bitrates: List[int] = [250, 500, 1000, 2500, 4000, 8000],
    test_files_count: int = -1,
    skip_vbr: bool = False,
) -> None:
    """
    Run tests across a range of crfs and bitrates using different encoders
    :param encs: 0 is control, rest are tests
    :param title: title of the experiment
    :param test_env: where to save the encoded files
    :param crfs: crfs to test across
    :param bitrates: bitrates to test across
    :return: None
    """
    stats_crf = []
    stats_bitrates = []

    if len(encs) == 0:
        raise ValueError("encs must have at least 1 encoder")

    for enc in tqdm(encs, desc=f"Running tests for {title}", leave=None):
        enc_index = encs.index(enc)

        enc_env = test_env + f"{enc_index}/"

        if not os.path.exists(enc_env):
            os.mkdir(enc_env)

        if not skip_vbr:
            bitrate_env = enc_env + "bitrate/"
            if not os.path.exists(bitrate_env):
                os.mkdir(bitrate_env)

            for bitrate in tqdm(bitrates, desc="Bitrates", leave=None):
                enc.bitrate = bitrate
                enc.passes = 3
                enc.rate_distribution = EncoderRateDistribution.VBR
                version = f"enc{enc_index}_{bitrate}kbs"
                if enc_index == 0:
                    version = f"control_{bitrate}kbs"
                stats_bitrates += run_tests(
                    enc,
                    version,
                    test_env=bitrate_env,
                    test_files_count=test_files_count,
                )

        crf_env = enc_env + "crf/"
        if not os.path.exists(crf_env):
            os.mkdir(crf_env)

        for crf in tqdm(crfs, desc="CRF", leave=None):
            enc.crf = crf
            enc.passes = 1
            enc.rate_distribution = EncoderRateDistribution.CQ

            version = f"enc{enc_index}_{crf}crf"
            if enc_index == 0:
                version = f"control_{crf}crf"
            stats_crf += run_tests(
                enc, version, test_env=crf_env, test_files_count=test_files_count
            )

    report(stats_crf, experiment_name=f"{title} CRF")
    save_stats(stats_crf, experiment_name=f"{title} CRF", test_env=test_env)

    if not skip_vbr:
        report(stats_bitrates, experiment_name=f"{title} Bitrates")
        save_stats(
            stats_bitrates, experiment_name=f"{title} Bitrates", test_env=test_env
        )


def read_report(report_path: str) -> DataFrame:
    with open(report_path) as f:
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
                "time_encoding",
            )
        }

    df = pd.DataFrame(data)

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


if __name__ == "__main__":
    # test_env = get_test_env()
    # experiment_name = "Testing speed presets, 12 is control"
    #
    # enc = AbstractEncoderSvtenc()
    # enc.update(speed=12, crf=30, passes=1, rate_distribution=RateDistribution.CQ)
    # enc.threads = 12
    #
    # stats = run_tests(enc, version="control", test_env=test_env)
    #
    # enc.speed = 4
    #
    # stats += run_tests(enc, "speed4", test_env=test_env)
    #
    # enc.speed = 8
    #
    # stats += run_tests(enc, "speed8", test_env=test_env)
    #
    # enc.speed = 2
    #
    # stats += run_tests(enc, "speed2", test_env=test_env)
    #
    # save_stats(stats, experiment_name=experiment_name, test_env=test_env)
    #
    # report(stat_reports=stats, experiment_name=experiment_name)
    pass
