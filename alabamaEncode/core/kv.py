import json
import os


class AlabamaKv(object):
    """
    AlabamaKv is a key-value store that stores data in a bucket, each bucket is file in a folder. Stored in json format.
    It is used to store data between runs of alabamaEncode. Saving to files immediately because making this
    thread safe is not worth it/needed.
    Prototypes:
    __init__(folder for buckets)
    set(bucket, key, value)
    get(bucket, key) -> str
    get_all(bucket) -> dict
    exists(bucket, key) -> bool
    get_global(key) -> str  # shortcut for get("kv", key)
    set_global(key, value)  # shortcut for set("kv", key, value)
    """

    def __init__(self, folder):
        self.folder = folder
        if not os.path.exists(self.folder):
            os.makedirs(self.folder)

    def get_global(self, key):
        return self.get("kv", key)

    def set_global(self, key, value):
        return self.set("kv", key, value)

    def set(self, bucket, key, value):
        b = self._load(bucket)
        b[key] = value
        self._save(bucket, b)

    def get(self, bucket, key) -> [str | None]:
        b = self._load(bucket)
        if key not in b:
            return None
        return b[key]

    def get_all(self, bucket):
        b = self._load(bucket)
        return b

    def exists(self, bucket, key):
        b = self._load(bucket)
        return key in b

    def _load(self, bucket_name: str) -> dict:
        bucket_path = os.path.join(self.folder, bucket_name + ".json")
        if os.path.exists(bucket_path):
            with open(bucket_path) as f:
                return json.load(f)
        else:
            return {}

    def _save(self, name: str, content):
        bucket_path = os.path.join(self.folder, name + ".json")
        with open(bucket_path, "w") as f:
            json.dump(content, f)
