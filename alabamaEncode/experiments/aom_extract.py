from alabamaEncode.ai_vmaf.aom_firstpass import aom_extract_firstpass_data
from alabamaEncode.scene.chunk import ChunkObject

if __name__ == "__main__":
    chunk = ChunkObject(
        path="/mnt/data/objective-1-fast/Netflix_RollerCoaster_1280x720_60fps_8bit_420_60f.y4m"
    )

    aom_extract_firstpass_data(chunk)
