import asyncio
import aiohttp

import lbrynet.conf

class MetadataServer:
    """ We refer to the server that hosts all the comment data
        and other good stuff as being the 'MetadataServer'. We use terminology
        such as "claim data", but what we are in fact referring to is
        the metadata that goes alongside the claims. Said metadata comprises
        things such as likes or dislikes, and more importantly,
        the comments.
    """
    _request_id = 0
    _session = None

    @classmethod
    async def _make_request(cls, method: str, params: dict = None):
        """ Asynchronously makes a request to the metadata server using the
        incremented ID, as well as the given method and parameters.

        Note - The API's methods and parameters are documented online at [https://ocornoc.github.io/lbry-comments]

        :param method: API method to call from the comments server.
        :param params: Parameters for the given method.
        :return: The response received from the server
        """


    def __init__(self, server_url: str = None):
        """
        :param server_url: Location of the server. Note that in the future
          this will be multiple, however for now it's just the one.
        """
        self._server_url = server_url
        self._server_status = None

    @property
    def server_url(self):
        return self._server_url

    @property
    def status(self):


