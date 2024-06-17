import os

from alabamaEncode.core.util.bin_utils import get_binary, register_bin
from alabamaEncode.core.util.cli_executor import run_cli
from alabamaEncode.encoder.impl.Svtenc import EncoderSvt


def build_svt():
    build_dir = "~/.alabamaEncoder/build"
    bin_dir = "~/.alabamaEncoder/bin"
    git_url = "https://gitlab.com/AOMediaCodec/SVT-AV1.git"

    build_dir = os.path.expanduser(build_dir)
    bin_dir = os.path.expanduser(bin_dir)

    bin_name = "SvtAv1EncApp"
    bin_path = bin_dir + "/" + bin_name

    if not os.path.exists(build_dir):
        os.makedirs(build_dir)

    if not os.path.exists(bin_dir):
        os.makedirs(bin_dir)

    repo_path = build_dir + "/SVT-AV1"

    if not os.path.exists(repo_path):
        print("Cloning SVT repo")
        os.system(
            f"{get_binary('git')} clone --depth 1 --single-branch --branch master --no-tags {git_url} \"{repo_path}\""
        )
    else:
        print("Updaing SVT repo")
        os.system(f"{get_binary('git')} pull \"{repo_path}\"")

    if not os.path.exists(repo_path):
        print("Failed to clone SVT repo")
        return

    print("Building SVT")
    os.system(
        f"cd {repo_path}/Build/linux && ./build.sh clean &&"
        f" ./build.sh cc=clang cxx=clang++ enable-lto static native release"
    )

    new_bin_path = repo_path + "/Bin/Release/SvtAv1EncApp"

    if os.path.exists(new_bin_path):
        os.system(f"chmod +x {new_bin_path}")
        register_bin("SvtAv1EncApp", new_bin_path)
        print(f"Just compiled SVT: {EncoderSvt().get_version()}")
        os.rename(new_bin_path, bin_path)
    else:
        print("Failed to compile SVT")


def build_vmaf():
    # build is a strong word...
    bin_url = "https://github.com/Netflix/vmaf/releases/download/v3.0.0/vmaf"

    bin_dir = os.path.expanduser("~/.alabamaEncoder/bin")
    bin_name = "vmaf"
    bin_path = bin_dir + "/" + bin_name

    if not os.path.exists(bin_dir):
        os.makedirs(bin_dir)
    import requests

    print("Downloading VMAF")

    r = requests.get(bin_url, allow_redirects=True)
    open(bin_path, "wb").write(r.content)
    if not os.path.exists(bin_path):
        print("Failed to download VMAF")
        return
    os.system(f"chmod +x {bin_path}")
    version = run_cli(f"{bin_path} -v").get_output()
    print(f"Just downloaded VMAF: {version}")


if __name__ == "__main__":
    # build_svt()
    build_vmaf()
