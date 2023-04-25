# Experimenting with quantization matrices (enable-qm) in SVT-AV1

## TL;DR

* when doing capped crf/crf on live action content (especially >1080p) `--enable-qm 1 --qm-min 0 --qm-max 8` can shave off ~10% for free
* `--enable-qm 1 --qm-min 0 --qm-max 15` when encoding anime
* when not sure/other type of content using `--enable-qm 1` yields **safe** results

## intro

#### notes:

* written as `min-max`, so `8-15` is `--qm_min 8 --qm_max 15`
* 8-15 is the default when using enable-qm=1
* using SVT-AV1 fca4581 (release)
* done on 200 frame chunks of a 1080p/4k 24fps video, Blu-ray quality
* all vbr was done with `--bias-pct 90` and three passes
* DB rate = size / vmaf; can be though as a "bang for your buck" metric
* vmaf should be taken with a fat grain of salt, since it relies on fuzzy deep learning logic that can (and is) tricked by encoders often

#### things I wish I did different:

* tune grain synth per clip, especially in the brighter live action since it looks blured

### crf params
`--input-depth 10 --crf 18 --tune 0 --film-grain 3 --preset 4 --qm-min x --qm-max x --enable-qm x --scd 0 --enable-overlays 1 --passes 1`

### vbr params
` --input-depth 10 --keyint 240 --rc 1 --tbr x --bias-pct 90 --tune 0 --film-grain 3 --preset 4 --qm-min x --qm-max x --enable-qm x --scd 0 --passes 3`



# Tests:

## typical live action

| _CRF 18_ |  size  | kpbs | vmaf  | DB Change % |
|----------|:------:|:----:|:-----:|:-----------:|
| 8-15     | 1106kb | 1061 | 96.03 |   +3.99%    |
| 0-15     | 1023kb | 981  | 95.95 |   +11.12%   |
| 0-8      | 1015kb | 973  | 95.93 |   +11.99%   |
| disabled | 1152kb | 1105 | 96.03 |      -      |

subjective eye test: cant tell a difference between the 4

| _VBR 1Mbps_ |  size  | kpbs | vmaf  | DB Change % |
|-------------|:------:|:----:|:-----:|:-----------:|
| 8-15        | 1044kb | 1001 | 96.09 |   -0.19%    |
| 0-15        | 1047kb | 1004 | 96.06 |   -0.51%    |
| 0-8         | 1048kb | 1005 | 96.04 |   -0.62%    |
| disabled    | 1042kb | 1000 | 96.09 |      -      |

subjective eye test: cant tell a difference between the 4

## typical live action 4k

| _CRF 18_ |  size  | kpbs | vmaf  | DB Change % |
|----------|:------:|:----:|:-----:|:-----------:|
| 8-15     | 3045kb | 2921 | 96.04 |   +2.89%    |
| 0-15     | 2733kb | 2621 | 95.99 |   +12.79%   |
| 0-8      | 2685kb | 2575 | 95.93 |   +14.27%   |
| disabled | 3134kb | 3005 | 95.99 |      -      |

subjective eye test: cant tell a difference between the 4

| _VBR 4Mbps_ |  size  | kpbs | vmaf  | DB Change % |
|-------------|:------:|:----:|:-----:|:-----------:|
| 8-15        | 4124kb | 3955 | 96.21 |   -0.25%    |
| 0-15        | 4208kb | 4036 | 96.25 |   -2.25%    |
| 0-8         | 4223kb | 4050 | 96.24 |   -2.63%    |
| disabled    | 4113kb | 3944 | 96.20 |      -      |

subjective eye test: better than crf since it was forced to spend more bits, but cant tell a difference between the 4

## brighter typical live action

| _CRF 18_ |  size  | kpbs | vmaf  | DB Change % |
|----------|:------:|:----:|:-----:|:-----------:|
| 8-15     | 2205kb | 2115 | 99.87 |   +1.57%    |
| 0-15     | 2091kb | 2005 | 99.86 |   +6.65%    |
| 0-8      | 2068kb | 1983 | 99.86 |   +7.68%    |
| disabled | 2240kb | 2148 | 99.86 |      -      |

subjective eye test: side by side 8-15 does the best job at fine hairs, standalone cant tell them apart

| _VBR 1Mbps_ |  size  | kpbs | vmaf  | DB Change % |
|-------------|:------:|:----:|:-----:|:-----------:|
| 8-15        | 1034kb | 992  | 99.63 |   +0.11%    |
| 0-15        | 1032kb | 990  | 99.64 |   +0.31%    |
| 0-8         | 1034kb | 991  | 99.64 |   +0.12%    |
| disabled    | 1035kb | 993  | 99.62 |      -      |

subjective eye test: each has different motion artifacts here and there, but cant tell them apart

## high motion, heavy fx, action movie

| _CRF 18_ |  size  | kpbs | vmaf  | DB Change % |
|----------|:------:|:----:|:-----:|:-----------:|
| 8-15     | 3904kb | 3744 | 99.67 |    0.26%    |
| 0-15     | 3762kb | 3608 | 99.66 |    3.87%    |
| 0-8      | 3709kb | 3557 | 99.66 |    5.25%    |
| disabled | 3914kb | 3753 | 99.67 |      -      |

subjective eye test: av1 destroyed fine details as always, couldn't really tell a difference between the 4

| _VBR 2Mbps_ |  size  | kpbs | vmaf  | DB Change % |
|-------------|:------:|:----:|:-----:|:-----------:|
| 8-15        | 2043kb | 1959 | 99.25 |   -0.07%    |
| 0-15        | 2049kb | 1965 | 99.23 |   -0.38%    |
| 0-8         | 2055kb | 1971 | 99.24 |   -0.59%    |
| disabled    | 2041kb | 1958 | 99.22 |      -      |

subjective eye test: looks a little worse than crf, but the motion hides it well. side by side is hard to tell

## 2d animation (anime)

| _CRF 18_ |  size  | kpbs | vmaf  | DB Change % |
|----------|:------:|:----:|:-----:|:-----------:|
| 8-15     | 4309kb | 4132 | 97.65 |   +5.18%    |
| 0-15     | 4646kb | 4456 | 97.87 |    -2.0%    |
| 0-8      | 4671kb | 4480 | 97.86 |   -2.56%    |
| disabled | 4546kb | 4370 | 97.68 |      -      |

subjective eye test: side by side looks the same as input

| _VBR 1.5Mbps_ |  size  | kpbs | vmaf  | DB Change % |
|---------------|:------:|:----:|:-----:|:-----------:|
| 8-15          | 1453kb | 1393 | 94.96 |   -0.01%    |
| 0-15          | 1438kb | 1380 | 95.50 |   +1.59%    |
| 0-8           | 1458kb | 1399 | 95.39 |    +0.1%    |
| disabled      | 1450kb | 1390 | 94.77 |      -      |

subjective eye test: there is more mosqito noise compared to crf, but they look very similar


## Stop-motion animation

| _CRF 18_ |  size  | kpbs | vmaf  | DB Change % |
|----------|:------:|:----:|:-----:|:-----------:|
| 8-15     | 6102kb | 5853 | 96.85 |   +2.38%    |
| 0-15     | 5737kb | 5502 | 96.66 |   +8.04%    |
| 0-8      | 5706kb | 5473 | 96.63 |   +8.51%    |
| disabled | 6251kb | 5995 | 96.85 |      -      |

subjective eye test: no noticeable difference, imo 0-15 represents fine details better

| _VBR 3Mbps_ |  size  | kpbs | vmaf  | DB Change % |
|-------------|:------:|:----:|:-----:|:-----------:|
| 8-15        | 3063kb | 2938 | 94.66 |   +0.41%    |
| 0-15        | 3128kb | 3000 | 94.84 |   -1.51%    |
| 0-8         | 3154kb | 3024 | 94.84 |   -2.36%    |
| disabled    | 3072kb | 2946 | 94.55 |      -      |

subjective eye test: disabled has more blocking artifacts, otherwise no noticeable difference
