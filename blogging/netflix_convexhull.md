### arcane s01e02

### h264

| bitrate | res       | vmeth |
|---------|-----------|-------|
| 58      | 480x270   | 45    |
| 78      | 608x342   | 55    |
| 98      | 768x432   | 62    |
| 127     | 768x432   | 68    |
| 248     | 960x540   | 81    |
| 385     | 1280x720  | 87    |
| 586     | 1280x720  | 90    |
| 1121    | 1920x1080 | 93    |
| 1876    | 1920x1080 | 95    |
| 3697    | 1920x1080 | 96    |

### vp9

| bitrate | res       | vmeth |
|---------|-----------|-------|
| 95      | 768x432   | 73    | 
| 117     | 960x540   | 78    | 
| 200     | 960x540   | 84    | 
| 346     | 1280x720  | 91    | 
| 674     | 1920x1080 | 95    |

### av1

| bitrate | res | vmeth |
|---------|-----|-------|
| -       | -   | -     |

### hevc

| bitrate | res | vmeth |
|---------|-----|-------|
| -       | -   | -     |

## speculation on the nf per scene encode process

#### The goal is to have

1. good quality/bitrate separation on the bitrate ladder
2. optimal resolution for the targeted quality level (vmaf score)
3. a bitrate ladder granular enough to allow smooth bitrate switching

##### why?

Matching a vmaf target to resolution is important because it allows us to maximize the convex hull of the vmaf score.
<Br>
Picking a good resolution alone can yield 20% more efficient bitrate usage, especially on lower bitrates.
<Br>
And a separated bitrate ladder is important
since we want to efficiently use the bitrate budget and maximize the quality per bit
<Br>
This is enabled by guiding the bitrate ladder creation by quality levels, not arbitrary numbers.

### my rough idea on how to do it

- preform scene detection on the video
- group the scenes into ~10 second chunks,
    - fewer chunks means less overhead, but potentially leads to less accurate results
- encode each chunk at each res & crf
    - assuming an 18–55 crf range, encoding every other crf, and 6 resolutions.
      That's 6x18=108 encodes per chunk of
      video
- get a curated list of vmaf's we want to target (e.g., steal from the netflix table above)
- The trellis would go something like:
    - per each resolution, per each vmaf score, do a trellis that matches vmaf score as close as possible
    - that's 10 vmaf's * six resolutions = 60 trellis paths
    - now we need to extract the best 10 trellis paths (one per each vmaf) that have the best bitrate/quality separation
    - for each resolution trellis path in the same vmaf group:
        - sort by: avg chunk vmaf error from the vmaf group, difference of bitrate from the previous path
        - pick the top one
        - (for the first vmaf group, lets say 96, don't worry about the bitrate difference, since there is no previous
          path to separate from)
    - repeat above until we have all 10 paths for each vmaf group
- retrieve the trellised chunks and concat them into the 10 video files, one per each vmaf group
- dash packaging

### some notes

- Encoding the whole crf range per resolution is wasteful and bruteforce-ish, most of them will be discarded.
  <Br>
  You could develop a heuristic to limit the search space
- Convex hull for newer codecs like av1 is shifted to higher resolutions a lot,
  <Br>
  this is because the new transforms/macro blocks/partitioning scale really well with resolution.
  <Br>
  So you could limit the resolutions to 4, and still get a good result, while saving 2*18=36 encodes per chunk.
  <Br>
  This also means that picking the right resolutions is less important.
  <Br>
  For example, convex hulls for av1 only need it lower than 1080p bellow 70 vmaf or so
  <Br>
  This also works in the other direction where if you encode at 1440p you can save bitrate.
  <Br>
  Since the classic wisdom of "lower res means less encoder overhead" is actually inverted (mostly) for av1.
  Higher res'es allow the transforms to stretch their legs and do their thing.
- Netflix's table has 10 vmaf quality targets, imo that is too much.
  <Br>
  Only benefit I see is maintaining the absolute best quality for spotty connections.
  <Br>
  Since internet bandwidth doesn't really scale linearly,
  ~2x bitrate jumps like they have it are probably redundant.
  <Br>
  Although I don't run a streaming service, so there are probably other good reasons why they do it this way.
  <Br>
  _PS If you know ill love to hear it._
- You cant really target lower vmaf's with av1, in my anignotal testing vmaf 80 usually means 100kb/s 