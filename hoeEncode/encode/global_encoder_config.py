
class EncoderConfig:
    def __init__(self, aom_lavifh_path="aomenc", svtav1_path="yes"):
        self.aom_lavifh_path = aom_lavifh_path
        self.svtav1_path = svtav1_path


configSingleton = EncoderConfig()
