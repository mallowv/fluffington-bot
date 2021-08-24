"""Library to interact asynchronously with tio.run"""

from functools import partial
from urllib.request import Request, urlopen
from gzip import decompress
from zlib import compress

import aiohttp

to_bytes = partial(bytes, encoding="utf-8")


def _to_tio_string(couple: tuple) -> bytes:
    """Generates a valid TIO "bytes-string" (utf-8) for a Variable or a File"""

    name, obj = couple[0], couple[1]
    if not obj:
        return b""
    elif type(obj) == list:
        content = ["V" + name, str(len(obj))] + obj
        return to_bytes("\0".join(content) + "\0")
    else:
        return to_bytes(f"F{name}\0{len(to_bytes(obj))}\0{obj}\0")


class Tio:
    """Represents the Tio instance where code is executed"""

    def __init__(
        self,
        backend="https://tio.run/cgi-bin/run/api/",
        json="https://tio.run/languages.json",
    ):
        self.backend = backend
        self.json = json

    @staticmethod
    def new_request(
        language: str,
        code: str,
        inputs: str = "",
        cflags: list = [],
        options: list = [],
        args: list = [],
    ):
        """Returns a DEFLATE compressed bytestring ready to be sent"""

        strings = {
            "lang": [language],
            ".code.tio": code,
            ".input.tio": inputs,  # Lists of lines to give when input is asked
            "TIO_CFLAGS": cflags,
            "TIO_OPTIONS": options,
            "args": args,
        }

        bytes_ = (
            b"".join(map(_to_tio_string, zip(strings.keys(), strings.values()))) + b"R"
        )

        return compress(bytes_, 9)[2:-4]

    async def async_send(self, request) -> str:
        """Sends given request and returns tio output (async)"""

        async with aiohttp.ClientSession() as client_session:
            async with client_session.post(self.backend, data=request) as res:

                data = await res.read()
                data = data.decode("utf-8")

                return data.replace(data[:16], "")  # remove token

    def send(self, request) -> str:
        """Sends given request and returns tio output (sync)"""

        req = Request(url=self.backend, data=request, method="POST")

        with urlopen(req) as res:

            data = res.read()
            data = decompress(data).decode("utf-8")

            data = data.replace(data[:16], "")
            start, end = data.rindex("Real time: "), data.rindex("%\nExit code: ")
            data = data[:start] + data[end + 2 :]
            return data
