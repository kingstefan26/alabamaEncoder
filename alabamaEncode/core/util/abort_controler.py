class AbortControler:
    def __init__(self):
        self.aborted = False

    def abort(self):
        self.aborted = True
