class RdPoint:
    rate: int
    target_rate: int
    vmaf: float
    ssim: float
    psnr: float
    butter: float
    speed: int
    file_path: str
    grain: int

    def __str__(self):
        return f"rate: {self.rate} vmaf: {self.vmaf} ssim: {self.ssim} psnr: {self.psnr} speed: {self.speed} file_path: {self.file_path}"
