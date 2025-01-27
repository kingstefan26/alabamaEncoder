from alabamaEncode.scene.scene_detection import scene_detect


def do_scene_detection(ctx):
    ctx.chunk_sequence = scene_detect(
        input_file=ctx.input_file,
        cache_file_path=ctx.temp_folder + "scene_cache.json",
        max_scene_length=ctx.max_scene_length,
        start_offset=ctx.start_offset,
        end_offset=ctx.end_offset,
        override_bad_wrong_cache_path=ctx.override_scenecache_path_check,
        static_length=ctx.statically_sized_scenes,
        static_length_size=ctx.max_scene_length,
        scene_merge=ctx.scene_merge,
    ).setup_paths(
        temp_folder=ctx.temp_folder,
        extension=ctx.get_encoder().get_chunk_file_extension(),
    )

    ctx.total_chunks = len(ctx.chunk_sequence.chunks)
    return ctx
