from alabamaEncode.parallel_execution.celery_app import app


def setup_celery(ctx):
    if ctx.use_celery:
        print("Using celery")
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # doesn't even have to be reachable
            s.connect(("10.255.255.255", 1))
            host_address = s.getsockname()[0]
        finally:
            s.close()
        print(f"Got lan ip: {host_address}")

        num_workers = app.control.inspect().active_queues()
        if num_workers is None:
            print("No workers detected, please start some")
            quit()
        print(f"Number of available workers: {len(num_workers)}")
    else:
        print(
            f"Using {ctx.prototype_encoder.get_pretty_name()} version: {ctx.prototype_encoder.get_version()}"
        )
    return ctx
