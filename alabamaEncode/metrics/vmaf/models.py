import os

from alabamaEncode.cli_executor import run_cli


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
    }

    return model_dict
