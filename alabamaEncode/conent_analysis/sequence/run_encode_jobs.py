import asyncio

from tqdm import tqdm

from alabamaEncode.conent_analysis.pipelines import get_refine_steps
from alabamaEncode.parallel_execution.execute_commands import execute_commands


async def run_encode_jobs(ctx):
    iter_counter = 0
    if ctx.dry_run:
        iter_counter = 2

    while ctx.chunk_sequence.sequence_integrity_check(
            kv=ctx.get_kv()
    ):
        iter_counter += 1
        if iter_counter > 3:
            print("Integrity check failed 3 times, aborting")
            quit()

        if len(ctx.chunk_jobs) > 0:
            print(
                f"Starting encoding of {len(ctx.chunk_jobs)} out of {len(ctx.chunk_sequence.chunks)} scenes"
            )
            saved_progress = ctx.get_kv().get_global("pbar_progress")
            pbar = tqdm(
                total=sum([c.chunk.length for c in ctx.chunk_jobs]),
                desc="Encoding",
                unit="frame",
                dynamic_ncols=True,
                unit_scale=True,
                smoothing=0,
                initial=saved_progress if saved_progress is not None else 0,
            )

            saved_total = ctx.get_kv().get_global("pbar_total")
            if saved_total is not None:
                pbar.total = saved_total

            saved_estimation = ctx.get_kv().get_global("pbar_estimation")
            if saved_estimation is not None:
                pbar.set_postfix(estimation=saved_estimation)

            pbar.refresh()

            def update_proc_done(num_finished_scenes):
                already_done = len(ctx.chunk_sequence.chunks) - len(
                    ctx.chunk_jobs
                )
                # self.websiteUpdate.update_proc_done(
                #     (
                #             (already_done + num_finished_scenes)
                #             / len(ctx.chunk_sequence.chunks)
                #     )
                #     * 100
                # )

            try:
                await asyncio.create_task(
                    execute_commands(
                        use_celery=ctx.use_celery,
                        command_objects=ctx.chunk_jobs,
                        multiprocess_workers=ctx.multiprocess_workers,
                        pin_to_cores=ctx.pin_to_cores,
                        finished_scene_callback=update_proc_done,
                        size_estimate_data=(
                            ctx.last_session_encoded_frames,
                            ctx.last_session_size_kb,
                        ),
                        throughput_scaling=ctx.throughput_scaling,
                        pbar=pbar,
                    )
                )
            except (KeyboardInterrupt, asyncio.exceptions.CancelledError):
                print("Keyboard interrupt, stopping")
                # kill all async tasks
                pbar.close()
                for task in asyncio.all_tasks():
                    task.cancel()

                # save pbar progress in kv
                kv = ctx.get_kv()
                kv.set_global("pbar_progress", pbar.n)
                if kv.get_global("pbar_total") is None:
                    kv.set_global("pbar_total", pbar.total)
                kv.set_global("pbar_estimation", pbar.postfix.get("estimation"))
                quit()

        for refine_step in get_refine_steps(ctx):
            refine_step(ctx, ctx.chunk_sequence)
    return ctx
