import os.path
from copy import copy

from CeleryApp import app
from hoeEncode.encode.ffmpeg.FfmpegUtil import syscmd, EncoderConfigObject, EncoderJob


# KummandObject has one abstract run method
class KummandObject:
    def run(self):
        raise NotImplementedError

    def get_dry_run(self) -> str:
        raise NotImplementedError

    def output_check(self, path: str):
        """
        Throws a runtime error if path does not exist
        :param path:
        :return:
        """
        if not os.path.exists(path):
            raise RuntimeError("FATAL: ENCODE FAILED, PATH: " + path)


# CliKummand is a KummandObject that runs a list of commands in a shell
class CliKummand(KummandObject):
    def __init__(self):
        self.kummands = []
        self.infiles = []
        self.outfiles = []

    def add(self, kummand):
        # if string add
        if isinstance(kummand, str):
            self.kummands.append(kummand)
        # if list add each
        elif isinstance(kummand, list):
            for k in kummand:
                self.kummands.append(k)

    def add_infile_dependency(self, infile):
        self.infiles.append(infile)

    def add_outfile_dependency(self, outfile):
        self.outfiles.append(outfile)

    def run(self):
        for file in self.infiles:
            if not os.path.exists(file):
                raise Exception("FATAL: FILE DEPENDENCY NOT SATISFIED, PATH:" + file)
        for out in self.outfiles:
            if os.path.exists(out):
                print("dependency satisfied, skipping: " + out)
                return

        for cvm in self.kummands:
            syscmd(cvm)
        for file1 in self.outfiles:
            if not os.path.exists(file1):
                raise Exception("FATAL: OUTPUT FILE DEPENDENCY NOT SATISFIED, PATH:" + file1)

    def get_dry_run(self):
        kumadnd = ''
        for k in self.kummands:
            kumadnd += k + ' && '
        return kumadnd

    def __str__(self):
        return " ".join(self.kummands)


@app.task(bind=True)
def run_kummad_on_celery(kummand: KummandObject):
    kummand.run()


def run_kummand(kummand: KummandObject):
    kummand.run()


def convex_svt(job: EncoderJob, config: EncoderConfigObject) -> KummandObject:
    from hoeEncode.ConvexHullEncoding.ConvexHull import ConvexKummand
    return ConvexKummand(job, config)


def gen_svt_kummands(job: EncoderJob, config: EncoderConfigObject) -> CliKummand:
    kummands = CliKummand()

    local_chunk = copy(job.chunk)

    kummands.add_infile_dependency(local_chunk.path)

    kommand = f'ffmpeg -y {local_chunk.get_ss_ffmpeg_command_pair()} -c:v libsvtav1 {config.crop_string} -threads 1 ' \
              f'-g 999 -b:v {config.bitrate} -passlogfile {config.temp_folder}{job.current_scene_index}svt'

    # Explainer
    # tune=0 - tune for PsychoVisual Optimization
    # scd=0 - disable scene change detection
    # enable-overlays=1 - enable additional overlay frame thing 😍
    # irefresh-type=1 - open gop
    # lp=1 - one thread
    svt_common_params = 'tune=0:scd=0:enable-overlays=1:irefresh-type=1:lp=1'

    # NOTE:
    # I use this svt_common_params thing cuz we don't need grain synth for the first pass + its faster

    if config.two_pass:
        kummands.add(kommand + f' -svtav1-params {svt_common_params} -preset 8 -pass 1 -pix_fmt yuv420p10le -an -f '
                               f'null /dev/null')
        kummands.add(kommand + f' -svtav1-params {svt_common_params}:film-grain=10 -preset 3 -pass 2 -pix_fmt '
                               f'yuv420p10le -an ' + job.encoded_scene_path)
    else:
        kummands.add(
            kommand + f' -svtav1-params {svt_common_params}:film-grain=5 -preset 3 -pix_fmt yuv420p10le -an '
            + job.encoded_scene_path
        )

    kummands.add_outfile_dependency(job.encoded_scene_path)

    return kummands
