# Testing enable-overlays

you can see data
in `/alabamaEncode/experiments/data/overlays/Testing SvtAv1 Overlays --enable-overlays=1, speed 4 CRF.json`
after analyzing the data using functions from `/alabamaEncode/experiments/Overlays.py`

# I conclude that `--enable-overlays 1` is harmful to size

### more in depth:

test was done across the whole crf range on objective-fast-1, speed 4, tune 1 (default) <br>
done by taking average differences between test and control and then averaging those, code linked
above

| metric        | how to interpret | % difference |
|---------------|------------------|--------------|
| VMAF 1%tile   | higher better    | 0.0064%      |
| size          | higher worse     | 11.21%       |
| VMAF          | higher better    | 0.07%        |
| SSIM          | higher better    | 0.02%        |
| Bits Per vmaf | higher worse     | 11.13%       |

## i welcome anyone to critique my testing methodology, lets discuss in issues!