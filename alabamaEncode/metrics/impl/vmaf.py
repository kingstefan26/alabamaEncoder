import json
import os
from statistics import mean

from alabamaEncode.core.bin_utils import get_binary
from alabamaEncode.core.bin_utils import register_bin
from alabamaEncode.core.cli_executor import run_cli, run_cli_parallel
from alabamaEncode.core.path import PathAlabama
from alabamaEncode.metrics.exception import VmafException
from alabamaEncode.metrics.metric import Metric
from alabamaEncode.metrics.options import MetricOptions
from alabamaEncode.metrics.result import MetricResult
from alabamaEncode.scene.chunk import ChunkObject


class VmafOptions(MetricOptions):
    def __init__(
        self,
        phone=False,
        uhd=False,
        neg=False,
        no_motion=False,
        **kwargs,
    ):
        self.phone = phone
        self.uhd = uhd
        self.neg = neg
        self.no_motion = no_motion
        super().__init__(**kwargs)

    def get_model(self) -> str:
        models = get_models()
        if self.no_motion:
            return f'path={models["normal_neg_nomotion"]}'
        if self.neg:
            if self.uhd:
                return f'path={models["uhd_neg"]}'
            if self.phone:
                return f'path={models["normal_neg"]}:name=phonevmaf:enable_transform'
            else:
                return f'path={models["normal_neg"]}'

        else:
            if self.uhd:
                return f'path={models["uhd"]}'
            if self.phone:
                return f'path={models["normal"]}:name=phonevmaf:enable_transform'
            else:
                return f'path={models["normal"]}'

    @staticmethod
    def test():
        print(VmafOptions().get_model())
        assert VmafOptions(uhd=True).get_model() != VmafOptions().get_model()
        assert VmafOptions(phone=True).get_model() != VmafOptions().get_model()
        assert VmafOptions(neg=True).get_model() != VmafOptions().get_model()


def calc_vmaf(
    chunk: ChunkObject,
    vmaf_options: VmafOptions,
    log_path="",
):
    assert vmaf_options is not None

    from alabamaEncode.metrics.calculate import get_input_pipes

    owo = get_input_pipes(chunk=chunk, options=vmaf_options)

    ref_pipe = owo["ref_pipe"]
    dist_pipe = owo["dist_pipe"]
    ref_command = owo["ref_command"]
    dist_command = owo["dist_command"]

    if log_path == "":
        log_path = f"/tmp/{os.path.basename(chunk.chunk_path)}.vmaflog"

    vmaf_command = (
        f'{get_binary("vmaf")} -q --json --output "{log_path}" --model {vmaf_options.get_model()} '
        f"--reference {ref_pipe} "
        f"--distorted {dist_pipe}"
        f" --threads {vmaf_options.threads}"
    )

    cli_results = run_cli_parallel(
        [
            ref_command,
            dist_command,
            vmaf_command,
        ]
    )

    from alabamaEncode.metrics.calculate import cleanup_input_pipes

    cleanup_input_pipes(owo)

    for c in cli_results:
        try:
            c.verify()
        except RuntimeError as e:
            raise VmafException(
                f"Could not run vmaf command: {e}, {[c.output for c in cli_results]}"
            )

    try:
        log_decoded = json.load(open(log_path))
    except (json.decoder.JSONDecodeError, FileNotFoundError):
        raise VmafException(
            f"Could not decode vmaf log: {log_path}, {[c.output for c in cli_results]}"
        )

    os.remove(log_path)

    result = VmafResult(
        pooled_metrics=log_decoded["pooled_metrics"],
        _frames=log_decoded["frames"],
        fps=log_decoded["fps"],
    )
    return result


class VmafResult(MetricResult):
    def __init__(self, _frames=None, pooled_metrics=None, fps=None):
        if pooled_metrics is None:
            pooled_metrics = {}

        self.fps = fps

        if _frames is not None:
            frames = []
            for frame in _frames:
                if "vmaf" in frame["metrics"]:
                    frames.append([frame["frameNum"], frame["metrics"]["vmaf"]])
                else:
                    frames.append([frame["frameNum"], frame["metrics"]["phonevmaf"]])
            frames.sort(key=lambda x: x[0])
            # calc 1 5 10 25 50 percentiles
            vmaf_scores = [x[1] for x in frames]
            vmaf_scores.sort()
            self.percentile_1 = vmaf_scores[int(len(vmaf_scores) * 0.01)]
            self.percentile_5 = vmaf_scores[int(len(vmaf_scores) * 0.05)]
            self.percentile_10 = vmaf_scores[int(len(vmaf_scores) * 0.1)]
            self.percentile_25 = vmaf_scores[int(len(vmaf_scores) * 0.25)]
            self.percentile_50 = vmaf_scores[int(len(vmaf_scores) * 0.5)]

            if "vmaf" in pooled_metrics:
                self.mean = pooled_metrics["vmaf"]["mean"]
                self.harmonic_mean = pooled_metrics["vmaf"]["harmonic_mean"]
            else:
                self.mean = mean([x[1] for x in frames])
                self.harmonic_mean = 1 / mean([1 / x[1] for x in frames if x[1] != 0])

            self.max = max([x[1] for x in frames])
            self.min = min([x[1] for x in frames])

            self.std_dev = 0
            for frame in frames:
                self.std_dev += (frame[1] - self.mean) ** 2
            self.std_dev /= len(frames)
            self.std_dev **= 0.5

    def __str__(self):
        return f"{self.mean}"

    def __repr__(self):
        return (
            f"VmafResult(mean={self.mean},"
            f" fps={self.fps},"
            f" harmonic_mean={self.harmonic_mean},"
            f" prct_1={self.percentile_1},"
            f" prct_5={self.percentile_5},"
            f" std_dev={self.std_dev})"
        )


if __name__ == "__main__":
    from alabamaEncode.metrics.calculate import calculate_metric

    register_bin("vmaf", "/home/kokoniara/.local/opt/vmaf")

    reference_path = PathAlabama("/mnt/data/objective-1-fast/MINECRAFT_60f_420.y4m")
    distorted_path = PathAlabama(
        "/mnt/data/objective-1-fast/minecruft_test_encode_av1.mkv"
    )

    print("calcing phone vmaf with 1080p comparison display")
    result: VmafResult = calculate_metric(
        reference_path=reference_path,
        distorted_path=distorted_path,
        options=VmafOptions(phone=True, threads=10),
        metric=Metric.VMAF,
    )
    print(result.mean)
    print(result.harmonic_mean)
    print(result.percentile_1)
    # etc with different statistical representations
    print(result.__repr__())

    print("calcing normal vmaf with 1080p comparison display")
    a = calculate_metric(
        reference_path=reference_path,
        distorted_path=distorted_path,
        options=VmafOptions(threads=10),
        metric=Metric.VMAF,
    )
    print(a.__repr__())

    print("calcing uhd vmaf with 4k comparison display")
    a = calculate_metric(
        reference_path=reference_path,
        distorted_path=distorted_path,
        options=VmafOptions(uhd=True, threads=10),
        metric=Metric.VMAF,
    )
    print(a.__repr__())

    print("Using chunk object, 720p reference display and mobile model")
    chunk = ChunkObject(path=reference_path.path)
    chunk.chunk_path = distorted_path.path
    a = calculate_metric(
        chunk=chunk,
        options=VmafOptions(phone=True, threads=10),
        metric=Metric.VMAF,
    )
    print(a.__repr__())


def get_models() -> dict[str, str]:
    links = [
        [
            "https://github.com/Netflix/vmaf/raw/master/model/vmaf_4k_v0.6.1.json",
            "vmaf_4k_v0.6.1.json",
        ],
        [
            "https://github.com/Netflix/vmaf/raw/master/model/vmaf_v0.6.1.json",
            "vmaf_v0.6.1.json",
        ],
        [
            "https://github.com/Netflix/vmaf/raw/master/model/vmaf_4k_v0.6.1neg.json",
            "vmaf_4k_v0.6.1neg.json",
        ],
        [
            "https://github.com/Netflix/vmaf/raw/master/model/vmaf_v0.6.1neg.json",
            "vmaf_v0.6.1neg.json",
        ],
        [
            "https://github.com/kingstefan26/python-video-split-/raw/master/vmaf_v0.6.1neg-nomotion.json",
            "vmaf_v0.6.1neg-nomotion.json",
        ],
    ]

    models_dir = os.path.expanduser("~/vmaf_models")
    if not os.path.exists(models_dir):
        os.makedirs(models_dir)

    try:
        for link in links:
            if not os.path.exists(os.path.join(models_dir, link[1])):
                print("Downloading VMAF model")
                run_cli(
                    f"wget -O {models_dir}/{link[1]} {link[0]}"
                )  # TsODO: WINDOWS SUPPORT

        for link in links:
            if not os.path.exists(os.path.join(models_dir, link[1])):
                raise FileNotFoundError(f"Something went wrong accessing {link[1]}")
    except Exception as e:
        raise RuntimeError(f"Failed downloading VMAF models, {e}")

    # turn the model paths into absolute paths
    for link in links:
        link[1] = os.path.join(models_dir, link[1])

    model_dict = {
        "uhd": links[0][1],
        "normal": links[1][1],
        "uhd_neg": links[2][1],
        "normal_neg": links[3][1],
        "normal_neg_nomotion": links[4][1],
    }

    return model_dict
