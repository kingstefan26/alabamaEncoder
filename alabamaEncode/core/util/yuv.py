from collections import namedtuple

# https://github.com/ticapix/python-y4m

class Frame(namedtuple('Frame', ['buffer', 'headers', 'count'])):
    def __repr__(self):
        return '<frame %d: %dx%d>' % (self.count, self.headers['H'], self.headers['W'])

class Reader(object):
    def __init__(self, callback, verbose=False):
        self._callback = callback
        self._stream_headers = None
        self._data = bytes()
        self._count = 0
        self._verbose = verbose

    def _print(self, *args):
        if self._verbose:
            print('Y4M Reader:', ' '.join([str(e) for e in args]))

    def decode(self, data):
        assert isinstance(data, bytes)
        self._data += data
        if self._stream_headers is None:
            self._decode_stream_headers()
            if self._stream_headers is not None:
                self._print('detected stream with headers:', self._stream_headers)
        if self._stream_headers is not None:
            frame = self._decode_frame()
            while frame is not None:
                self._print(frame, 'decoded')
                self._callback(frame)
                frame = self._decode_frame()

    def _frame_size(self):
        if self._stream_headers['C'].startswith('420'):
            return self._stream_headers['W'] * self._stream_headers['H'] * 3 // 2
        elif self._stream_headers['C'].startswith('422'):
            return self._stream_headers['W'] * self._stream_headers['H'] * 2
        elif self._stream_headers['C'].startswith('444'):
            return self._stream_headers['W'] * self._stream_headers['H'] * 3
        raise f"only support I420, I422, I444 fourcc (not {self._stream_headers['C']})"

    def _decode_frame(self):
        if len(self._data) < self._frame_size():  # no point trying to parse
            return None
        toks = self._data.split(b'\n', 1)
        if len(toks) == 1:  # need more data
            self._print('weird: got plenty of data but no frame header found')
            return None
        headers = toks[0].split(b' ')
        # assert headers[0] == b'FRAME', 'expected FRAME (got %r)' % headers[0]
        frame_headers = self._stream_headers.copy()
        for header in headers[1:]:
            header = header.decode('ascii')
            frame_headers[header[0]] = header[1:]
        if len(toks[1]) < self._frame_size():  # need more data
            return None
        yuv = toks[1][0:self._frame_size()]
        self._data = toks[1][self._frame_size():]
        self._count += 1
        return Frame(yuv, frame_headers, self._count - 1)

    def _decode_stream_headers(self):
        toks = self._data.split(b'\n', 1)
        if len(toks) == 1:  # buffer all header data until eof
            return
        self._stream_headers = {}
        self._data = toks[1]  # save the beginning of the stream for later
        headers = toks[0].split(b' ')
        assert headers[0] == b'YUV4MPEG2', 'unknown type %s' % headers[0]
        for header in headers[1:]:
            header = header.decode('ascii')
            self._stream_headers[header[0]] = header[1:]
        assert 'W' in self._stream_headers, 'No width header'
        assert 'H' in self._stream_headers, 'No height header'
        assert 'F' in self._stream_headers, 'No frame-rate header'
        self._stream_headers['W'] = int(self._stream_headers['W'])
        self._stream_headers['H'] = int(self._stream_headers['H'])
        self._stream_headers['F'] = [int(n) for n in self._stream_headers['F'].split(':')]
        if 'A' in self._stream_headers:
            self._stream_headers['A'] = [int(n) for n in self._stream_headers['A'].split(':')]
        if 'C' not in self._stream_headers:
            self._stream_headers['C'] = '420jpeg'  # man yuv4mpeg
