import os
from datetime import datetime
from typing import List

from tqdm import tqdm

from alabamaEncode.encoders.RateDiss import RateDistribution
from alabamaEncode.encoders.encodeStats import EncodeStats
from alabamaEncode.encoders.encoder.AbstractEncoder import AbstractEncoder
from alabamaEncode.encoders.encoder.impl.Svtenc import AbstractEncoderSvtenc
from alabamaEncode.sceneSplit.ChunkOffset import ChunkObject

only_one = True


def get_test_files():
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

    if only_one:
        files = files[:3]

    return files


def get_test_env() -> str:
    pwd = os.getcwd()
    date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    test_env = pwd + f"/run_{date}/"
    if not os.path.exists(test_env):
        os.mkdir(test_env)

    return test_env


def run_tests(
    enc: AbstractEncoder, version: str = "control", test_env: str = get_test_env()
) -> List[EncodeStats]:
    """
    Run a test on all the files in the TEST_FILES env
    :param test_env: where to save the encoded files
    :param enc: Configured encoder object to run the test with
    :param version: version name to attach to the stats, e.g., "control"
    :return: a list of EncodeStats objects
    """
    paths = get_test_files()

    stat_reports = []

    curr_index = 0
    for input_path in tqdm(paths, desc=f"Running tests for {version}"):
        # create and set an output input_path for the video file
        # eg ./encode_test_2021-03-30_16-00-00/STARCRAFT_60f_420control.y4m
        basename = os.path.basename(input_path).split(".")[0]
        output_path = f"{test_env}{basename}_{version}{enc.get_chunk_file_extension()}"

        curr_index += 1

        # update the encoder with the new input and output paths
        enc.update(chunk=(ChunkObject(path=input_path)), output_path=output_path)

        # encode the chunk
        stats = enc.run(
            override_if_exists=False, calculate_vmaf=True, calcualte_ssim=True
        )

        # attach `version` & `basename` so we can compare later
        stats.version = version
        stats.basename = basename
        stat_reports.append(stats)

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
    # TODO: fix Object of type EncodeStats is not JSON serializable
    # with open(f"{test_env}{experiment_name}.json", "w") as f:
    #     json.dump(stat_reports, f)


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

        for stat in [*holder.sts, holder.control]:
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


if __name__ == "__main__":
    test_env = get_test_env()
    experiment_name = "Testing speed presets, 12 is control"

    enc = AbstractEncoderSvtenc()
    enc.update(speed=12, crf=30, passes=1, rate_distribution=RateDistribution.CQ)
    enc.threads = 12

    stats = run_tests(enc, version="control", test_env=test_env)

    enc.speed = 4

    stats += run_tests(enc, "speed4", test_env=test_env)

    enc.speed = 8

    stats += run_tests(enc, "speed8", test_env=test_env)

    enc.speed = 2

    stats += run_tests(enc, "speed2", test_env=test_env)

    save_stats(stats, experiment_name=experiment_name, test_env=test_env)

    report(stat_reports=stats, experiment_name=experiment_name)
