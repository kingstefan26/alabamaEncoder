# Experimenting with quantization matrices (enable-qm) in SVT-AV1

## TL;DR

needs to be redone since I added 0-8 tests & new clips 

* ~~use `--qm-min 0 --qm-max 15 --enable-qm 1` when using CRF~~
* ~~use `--qm-min 0 --qm-max 15 --enable-qm 1` on animation in VBR~~
* ~~in most cases, default value min max and `--enable-qm 1` does placebo similar as disabled, but with some free gains
  here and there. So I recommend keeping
  it enabled~~

## intro

notes:

* written as `min-max`, so `8-15` is `--qm_min 8 --qm_max 15`
* 8-15 is the default when using enable-qm=1
* using SVT-AV1 fca4581 (release)
* done on 200 frame chunks of a 1080p/4k 24fps video, Blu-ray quality
* all vbr was done with `--bias-pct 90` and three passes

crf params
used: `--input-depth 10 --crf 18 --tune 0 --film-grain 3 --preset 4 --qm-min x --qm-max x --enable-qm x --scd 0 --enable-overlays 1 --passes 1`

vbr params
used: ` --input-depth 10 --keyint 240 --rc 1 --tbr x --bias-pct 90 --tune 0 --film-grain 3 --preset 4 --qm-min x --qm-max x --enable-qm x --scd 0 --passes 3`



# Tests:

## typical live action

| _CRF 18_ |  size  | kpbs | vmaf  |
|----------|:------:|:----:|:-----:|
| 8-15     | 1106kb | 1061 | 96.03 |
| 0-15     | 1023kb | 981  | 95.95 |
| 0-8      | 1015kb | 973  | 95.93 |
| disabled | 1152kb | 1105 | 96.03 |

subjective eye test: cant tell a difference between the 4

| _VBR 1Mbps_ |  size  | kpbs | vmaf  |
|-------------|:------:|:----:|:-----:|
| 8-15        | 1044kb | 1001 | 96.09 |
| 0-15        | 1047kb | 1004 | 96.06 |
| 0-8         | 1048kb | 1005 | 96.04 |
| disabled    | 1042kb | 1000 | 96.09 |

subjective eye test: cant tell a difference between the 4

### Conclusion:

~~free gains for CRF, no significant effect on VBR~~

## typical live action 4k

| _CRF 18_ |  size  | kpbs | vmaf  |
|----------|:------:|:----:|:-----:|
| 8-15     | 3045kb | 2921 | 96.04 |
| 0-15     | 2733kb | 2621 | 95.99 |
| 0-8      | 2685kb | 2575 | 95.93 |
| disabled | 3134kb | 3005 | 95.99 |

subjective eye test: cant tell a difference between the 4

| _VBR 4Mbps_ |  size  | kpbs | vmaf  |
|-------------|:------:|:----:|:-----:|
| 8-15        | 4124kb | 3955 | 96.21 |
| 0-15        | 4208kb | 4036 | 96.25 |
| 0-8         | 4223kb | 4050 | 96.24 |
| disabled    | 4113kb | 3944 | 96.20 |

subjective eye test: better than crf since it was forced to spend more bits, but cant tell a difference between the 4

### Conclusion:
todo

## brighter typical live action

| _CRF 18_ |  size  | kpbs | vmaf  |
|----------|:------:|:----:|:-----:|
| 8-15     | 2205kb | 2115 | 99.87 |
| 0-15     | 2091kb | 2005 | 99.86 |
| 0-8      | 2068kb | 1983 | 99.86 |
| disabled | 2240kb | 2148 | 99.86 |

subjective eye test: side by side 8-15 does the best job at fine hairs, standalone cant tell them apart

| _VBR 1Mbps_ |  size  | kpbs | vmaf  |
|-------------|:------:|:----:|:-----:|
| 8-15        | 1034kb | 992  | 99.63 |
| 0-15        | 1032kb | 990  | 99.64 |
| 0-8         | 1034kb | 991  | 99.64 |
| disabled    | 1035kb | 993  | 99.62 |

subjective eye test: each has different motion artifacts here and there, but cant tell them apart

### Conclusion:
todo


## high motion, heavy fx, action movie

| _CRF 18_ |  size  | kpbs | vmaf  |
|----------|:------:|:----:|:-----:|
| 8-15     | 3904kb | 3744 | 99.67 |
| 0-15     | 3762kb | 3608 | 99.66 |
| 0-8      | 3709kb | 3557 | 99.66 |
| disabled | 3914kb | 3753 | 99.67 |

subjective eye test: av1 destroyed fine details as always, couldn't really tell a difference between the 4

| _VBR 2Mbps_ |  size  | kpbs | vmaf  |
|-------------|:------:|:----:|:-----:|
| 8-15        | 2043kb | 1959 | 99.25 |
| 0-15        | 2049kb | 1965 | 99.23 |
| 0-8         | 2055kb | 1971 | 99.24 |
| disabled    | 2041kb | 1958 | 99.22 |

subjective eye test: looks a little worse than crf, but the motion hides it well. side by side is hard to tell

### Conclusion:

~~same as above for live action, but more pronounced~~

## 2d animation (anime)

| _CRF 18_ |  size  | kpbs | vmaf  |
|----------|:------:|:----:|:-----:|
| 8-15     | 4309kb | 4132 | 97.65 |
| 0-15     | 4646kb | 4456 | 97.87 |
| 0-8      | 4671kb | 4480 | 97.86 |
| disabled | 4546kb | 4370 | 97.68 |

subjective eye test: side by side looks the same as input

| _VBR 1.5Mbps_ |  size  | kpbs | vmaf  |
|---------------|:------:|:----:|:-----:|
| 8-15          | 1453kb | 1393 | 94.96 |
| 0-15          | 1438kb | 1380 | 95.50 |
| 0-8           | 1458kb | 1399 | 95.39 |
| disabled      | 1450kb | 1390 | 94.77 |

subjective eye test: there is more mosqito noise compared to crf, but they look very similar

### Conclusion:

~~Use qm when using crf. Vbr 0-15 it seems to be the best metrics but more data needed~~

## Stop-motion animation

| _CRF 18_ |  size  | kpbs | vmaf  |
|----------|:------:|:----:|:-----:|
| 8-15     | 6102kb | 5853 | 96.85 |
| 0-15     | 5737kb | 5502 | 96.66 |
| 0-8      | 5706kb | 5473 | 96.63 |
| disabled | 6251kb | 5995 | 96.85 |

subjective eye test: no noticeable difference, imo 0-15 represents fine details better

| _VBR 3Mbps_ |  size  | kpbs | vmaf  |
|-------------|:------:|:----:|:-----:|
| 8-15        | 3063kb | 2938 | 94.66 |
| 0-15        | 3128kb | 3000 | 94.84 |
| 0-8         | 3154kb | 3024 | 94.84 |
| disabled    | 3072kb | 2946 | 94.55 |

subjective eye test: disabled has more blocking artifacts, otherwise no noticeable difference

### Conclusion:

~~Another win for crf 0-15. Same as for animation: vbr 0-15 maybe the best but more data needed~~