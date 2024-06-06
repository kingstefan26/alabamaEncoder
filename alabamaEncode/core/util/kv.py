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

    def set(self, bucket, key, value, individual_mode=False):
        if individual_mode:
            bucket_path = os.path.join(self.folder, bucket)
            if not os.path.exists(bucket_path):
                os.makedirs(bucket_path)
            key_path = os.path.join(bucket_path, f"{key}.json")
            with open(key_path, "w") as f:
                json.dump(value, f)
        else:
            bucket_content = self._load(bucket)
            bucket_content[key] = value
            bucket_path = os.path.join(self.folder, bucket + ".json")
            with open(bucket_path, "w") as f:
                json.dump(bucket_content, f)

    def get(self, bucket, key) -> [str | None]:
        b = self._load(bucket)
        if not isinstance(key, str):
            key = str(key)
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
        bucket_path = os.path.join(self.folder, bucket_name)
        single_file_path = bucket_path + ".json"
        if os.path.exists(single_file_path):
            with open(single_file_path, "r") as f:
                return json.load(f)
        elif os.path.exists(bucket_path):
            bucket_content = {}
            for key_file in os.listdir(bucket_path):
                key = os.path.splitext(key_file)[0]
                with open(os.path.join(bucket_path, key_file)) as f:
                    bucket_content[key] = json.load(f)
            return bucket_content
        else:
            return {}
