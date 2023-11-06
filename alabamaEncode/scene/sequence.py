import os
import random
from multiprocessing.pool import ThreadPool
from typing import List

from tqdm import tqdm

from alabamaEncode.parallelEncoding.execute_commands import execute_commands
from alabamaEncode.scene.chunk import ChunkObject


def verify_integrity(args) -> ChunkObject or None:
    """
    if chunk is invalid return it, else return None
    :param args:
    :return:
    """
    chunk, pbar = args
    result: bool = chunk.verify_integrity()
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
            c.chunk_path = f"{temp_folder}{c.chunk_index}{extension}"

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
                process_args = [(c, pbar) for c in seq_chunks]
                invalid_chunks: List[ChunkObject or None] = list(
                    pool.imap(verify_integrity, process_args)
                )

        invalid_chunks: List[ChunkObject] = [
            chunk for chunk in invalid_chunks if chunk is not None
        ]

        del_count = 0

        if len(invalid_chunks) > 0:
            for c in invalid_chunks:
                if os.path.exists(c.chunk_path):
                    os.remove(c.chunk_path)
                    del_count = +1
            return True
        print(f"Deleted {del_count} invalid files 😂")

        undone_chunks_count = len([c for c in self.chunks if not c.chunk_done])

        if undone_chunks_count > 0:
            print(
                f"Only {len(self.chunks) - undone_chunks_count}/{len(self.chunks)} chunks are done 😏"
            )
            return True

        print("All chunks passed integrity checks 🤓")
        return False

    async def process_chunks(
        self,
        ctx,
    ):
        command_objects = []
        from alabamaEncode.adaptive.executor import AdaptiveCommand

        for chunk in self.chunks:
            if not chunk.is_done():
                command_objects.append(AdaptiveCommand(ctx, chunk))

        # order chunks based on order
        if ctx.chunk_order == "random":
            random.shuffle(command_objects)
        elif ctx.chunk_order == "length_asc":
            command_objects.sort(key=lambda x: x.job.chunk.length)
        elif ctx.chunk_order == "length_desc":
            command_objects.sort(key=lambda x: x.job.chunk.length, reverse=True)
        elif ctx.chunk_order == "sequential":
            pass
        elif ctx.chunk_order == "sequential_reverse":
            command_objects.reverse()
        else:
            raise ValueError(f"Invalid chunk order: {ctx.chunk_order}")

        if len(command_objects) < 10:
            ctx.threads = os.cpu_count()

        print(f"Starting encoding of {len(command_objects)} scenes")

        await execute_commands(
            ctx.use_celery, command_objects, ctx.multiprocess_workers
        )
