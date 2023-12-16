import os.path

from alabamaEncode.conent_analysis.sequence.scrape_hdr_meta import scrape_hdr_metadata
from alabamaEncode.core.alabama import AlabamaContext

if __name__ == "__main__":
    ctx = AlabamaContext()
    ctx.prototype_encoder.hdr = True
    # ctx.raw_input_file = "/mnt/data/downloads/Halo.S01.2160p.UHD.BluRay.Remux.HDR.DV.HEVC.Atmos-PmP/Halo.S01E04.Homecoming.2160p.UHD.BluRay.Remux.HDR.DV.HEVC.Atmos-PmP.mkv"
    ctx.raw_input_file = "/mnt/data/downloads/Silo.S01E02.HDR.2160p.WEB.H265-GGEZ[rarbg]/silo.s01e02.hdr.2160p.web.h265-ggez.mkv"
    print(f"Extracting HDR10 metadata 🤩😳 for {os.path.basename(ctx.raw_input_file)}")
    ctx = scrape_hdr_metadata(ctx)

    print("matrix_coefficients", ctx.prototype_encoder.matrix_coefficients)
    print("color_primaries", ctx.prototype_encoder.color_primaries)
    print("transfer_characteristics", ctx.prototype_encoder.transfer_characteristics)
    print("chroma_sample_position", ctx.prototype_encoder.chroma_sample_position)
    print("max_content", ctx.prototype_encoder.maximum_content_light_level)
    print("max_average", ctx.prototype_encoder.maximum_frame_average_light_level)
    print("svt master display: ", ctx.prototype_encoder.svt_master_display)
