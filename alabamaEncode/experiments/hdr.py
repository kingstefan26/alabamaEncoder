import os.path

from alabamaEncode.core.alabama import AlabamaContext, scrape_hdr_metadata

if __name__ == "__main__":
    ctx = AlabamaContext()
    ctx.hdr = True
    # ctx.raw_input_file = "/mnt/data/downloads/Halo.S01.2160p.UHD.BluRay.Remux.HDR.DV.HEVC.Atmos-PmP/Halo.S01E04.Homecoming.2160p.UHD.BluRay.Remux.HDR.DV.HEVC.Atmos-PmP.mkv"
    ctx.raw_input_file = "/mnt/data/downloads/Silo.S01E02.HDR.2160p.WEB.H265-GGEZ[rarbg]/silo.s01e02.hdr.2160p.web.h265-ggez.mkv"
    print(f"Extracting HDR10 metadata 🤩😳 for {os.path.basename(ctx.raw_input_file)}")
    ctx = scrape_hdr_metadata(ctx)

    print("matrix_coefficients", ctx.matrix_coefficients)
    print("color_primaries", ctx.color_primaries)
    print("transfer_characteristics", ctx.transfer_characteristics)
    print("chroma_sample_position", ctx.chroma_sample_position)
    print("max_content", ctx.maximum_content_light_level)
    print("max_average", ctx.maximum_frame_average_light_level)
    print("svt master display: ", ctx.svt_master_display)
