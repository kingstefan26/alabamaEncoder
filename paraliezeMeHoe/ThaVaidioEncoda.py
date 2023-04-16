from CeleryApp import app
from hoeEncode.parallelEncoding.Command import CommandObject


@app.task(bind=True)
def run_command_on_celery(command: CommandObject):
    command.run()
