import os
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

    async def sequence_integrity_check(self, check_workers: int = 5) -> bool:
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
