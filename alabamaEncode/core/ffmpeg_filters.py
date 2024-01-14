class FfmpegFilters:
    def __init__(self):
        self._filters = []

    def get_str(self):
        filters = self._filters
        if len(filters) == 0:
            return ""
        filters = [f for f in filters if f is not None and f != ""]
        return ",".join(filters)

    def set_crop(self, x, y, width, height):
        for i in range(0, len(self._filters)):
            if self._filters[i].startswith("crop"):
                self._filters[i] = f"crop={width}:{height}:{x}:{y}"
                return
        self._filters.insert(f"crop={width}:{height}:{x}:{y}")

    def set_scale(self, width, height):
        for i in range(0, len(self._filters)):
            if self._filters[i].startswith("scale"):
                self._filters[i] = f"scale={width}:{height}"
                return
        self._filters.insert(f"scale={width}:{height}")
