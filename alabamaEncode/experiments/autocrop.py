from alabamaEncode.conent_analysis.sequence.autocrop import do_autocrop
from alabamaEncode.core.alabama import AlabamaContext

if __name__ == "__main__":
    print("AUTOCROP IMPLEMENTATION TEST")
    ctx = AlabamaContext()
    ctx.auto_crop = True
    ctx.input_file = "/mnt/data/downloads/Foundation.S02E08.2160p.WEB.h265-ETHEL[TGx]/Foundation.S02E08.2160p.WEB.h265-ETHEL.mkv"
    # ctx.input_file = "/mnt/data/downloads/Halo.S01.2160p.UHD.BluRay.Remux.HDR.DV.HEVC.Atmos-PmP/Halo.S01E04.Homecoming.2160p.UHD.BluRay.Remux.HDR.DV.HEVC.Atmos-PmP.mkv"
    ctx.output_file = "/home/kokoniara/showsEncode/HALO (2022)/s1/e4/out.webm"
    ctx = do_autocrop(ctx)
    print("Crop string: ", ctx.crop_string)
    assert (
        ctx.crop_string == "3840:1920:0:120"
    ), f"Expected 3840:1920:0:120 got {ctx.crop_string}"
