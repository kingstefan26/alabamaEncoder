import sys


def save_cli(ctx):
    with open(ctx.temp_folder + "cli_command", "w") as output_file:
        output_file.write(" ".join(sys.argv))
    return ctx
