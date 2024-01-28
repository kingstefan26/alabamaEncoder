import copy
import os
import random
from multiprocessing.pool import ThreadPool
from typing import List

from tqdm.asyncio import tqdm

from alabamaEncode.scene.chunk import ChunkObject


def verify_integrity_wrapper(args) -> ChunkObject or None:
    """
    if chunk is invalid return it, else return None
    :param args:
    :return:
    """
    chunk, pbar, sequence_length = args
    result: bool = chunk.verify_integrity(sequence_length)
    pbar.update()
    return chunk if result else None


class ChunkSequence:
    """
    A sequence of chunks.
    """

    def __init__(self, chunks: List[ChunkObject]):
        self.chunks = chunks
        self.input_file = ""

    def get_specific_chunk(self, index: int) -> ChunkObject:
        return self.chunks[index]

    def __len__(self):
        return len(self.chunks)

    def __getitem__(self, index):
        return self.chunks[index]

    def dump_json(self) -> str:
        """
        Dumps the sequence to json
        :return: string
        """
        import json

        d = {"chunks": [c.__dict__ for c in self.chunks], "input_file": self.input_file}
        return json.dumps(d)

    def load_json(self, json_load: str) -> "ChunkSequence":
        """
        Loads the sequence from json
        :param json_load: path to the json file to load
        :return: self
        """
        import json

        d = json.loads(json_load)

        self.chunks = [ChunkObject() for _ in d["chunks"]]
        for i, c in enumerate(d["chunks"]):
            self.chunks[i].__dict__ = c

        self.input_file = d["input_file"]
        return self

    def setup_paths(self, temp_folder: str, extension: str):
        """
        sets up the paths for the chunks, in the appropriate temp folder, and with the appropriate extension
        :param extension: .ivf .mkv etc.
        :param temp_folder: the temp folder to put the chunks in
        :return: Void
        """
        for c in self.chunks:
            # /home/user/encode/show/temp/1.ivf
            # or
            # /home/user/encode/show/temp/1.mkv
            c.chunk_path = os.path.join(temp_folder, f"{c.chunk_index}{extension}")

    def get_test_chunks_out_of_a_sequence(
        self, random_pick_count: int = 7
    ) -> List[ChunkObject]:
        """
        Get an equally distributed list of chunks from a sequence for testing, does not modify the original sequence
        :param random_pick_count: Number of random chunks to pick
        :return: List of Chunk objects
        """
        chunks_copy: List[ChunkObject] = copy.deepcopy(self.chunks)
        chunks_copy = chunks_copy[
            int(len(chunks_copy) * 0.2) : int(len(chunks_copy) * 0.8)
        ]

        if len(chunks_copy) > 10:
            # bases on length, remove every x scene from the list so its shorter
            chunks_copy = chunks_copy[:: int(len(chunks_copy) / 10)]

        random.shuffle(chunks_copy)
        chunks = chunks_copy[:random_pick_count]

        if len(chunks) == 0:
            print("Failed to shuffle chunks for analysis, using all")
            chunks = self.chunks

        return copy.deepcopy(chunks)

    def sequence_integrity_check(self, check_workers: int = 5) -> bool:
        """
        checks the integrity of the chunks, and removes any that are invalid, and see if all are done
        :param check_workers: number of workers to use for the check
        :return: true if there are broken chunks / not all chunks are done
        """

        print("Preforming integrity check 🥰")
        seq_chunks = list(self.chunks)
        total_chunks = len(seq_chunks)

        with tqdm(total=total_chunks, desc="Checking files", unit="file") as pbar:
            with ThreadPool(check_workers) as pool:
                process_args = [(c, pbar, len(self.chunks)) for c in seq_chunks]
                invalid_chunks: List[ChunkObject or None] = list(
                    pool.imap(verify_integrity_wrapper, process_args)
                )

        invalid_chunks: List[ChunkObject] = [
            chunk for chunk in invalid_chunks if chunk is not None
        ]

        del_count = 0

        if len(invalid_chunks) > 0:
            for c in invalid_chunks:
                if os.path.exists(c.chunk_path):
                    os.remove(c.chunk_path)
                    print(f"Deleted invalid file {c.chunk_path}")
                    del_count += 1
            return True

        if del_count > 0:
            print(f"Deleted {del_count} invalid files 😂")

        undone_chunks_count = len([c for c in self.chunks if not c.chunk_done])

        if undone_chunks_count > 0:
            print(
                f"Only {len(self.chunks) - undone_chunks_count}/{len(self.chunks)} chunks are done 😏"
            )
            return True

        print("All chunks passed integrity checks 🤓")
        return False
