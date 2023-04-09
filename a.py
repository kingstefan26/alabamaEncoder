import os
from datetime import datetime

from hoeEncode.encode.ffmpeg.FfmpegUtil import get_video_lenght

if __name__ == '__main__':

    # get all paths in the temp dir
    paths = os.listdir("/mnt/sda1/shows/The Chilling Adventures of Sabrina/Season 1")
    totalLenght = 0
    for file in paths:
        # if the file is a .ivf file then delete it
        if file.endswith('.mp4'):
            totalLenght += get_video_lenght(f"/mnt/sda1/shows/The Chilling Adventures of Sabrina/Season 1/{file}")

    # since totalLenght is in seconds, we need to convert it to hours, minutes and seconds
    date = datetime.fromtimestamp(totalLenght)
    print("Total time " + date.strftime("%H:%M:%S"))
