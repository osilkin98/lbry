import datetime

import logging
import aiohttp

log = logging.getLogger(__name__)


class MetadataClient:
    """ We refer to the server that hosts all the comment data
        and other good stuff as being the 'MetadataClient'. We use terminology
        such as "claim data", but what we are in fact referring to is
        the metadata that goes alongside the claims. Said metadata comprises
        things such as likes or dislikes, and more importantly,
        the comments.
    """
    __request_id: int = 0

    def __init__(self, server_url: str = None):
        self._server_url: str = server_url
        self.server_info: dict = {'last_updated': datetime.datetime.now(), 'status': None}
        self._is_connected = False

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @classmethod
    def request_id(cls) -> int:
        return cls.__request_id

    @classmethod
    def _make_request_body(cls, method: str, params: dict = None) -> dict:
        """ Creates a body for an HTTP request to the MetadataClient as
          documented. This method increments the request ID of the entire
          class after it generates the body.
        """
        body = {
            'jsonrpc': '2.0',
            'id': cls.__request_id,
            'method': method,
        }
        if params is not None:
            body['params'] = params
        cls.__request_id += 1
        return body

    @property
    def server_url(self) -> str:
        return self._server_url

    @property
    def status(self) -> dict:
        return self.server_info['status']

    async def update_server_status(self) -> dict:
        response = await self.make_request('status')
        self.server_info['last_updated'] = datetime.datetime.now()
        self.server_info['status'] = None if 'error' in response else response['result']
        return self.server_info

    async def make_request(self, method: str, params: dict = None, url: str = None) -> dict:
        """
        Makes a request to the Metadata API documented at [https://ocornoc.github.io/lbry-comments]

        :raises aiohttp.http.HttpProcessingError: If the HTTP response is anything besides 200
        :return: JSONRPC response
        """
        url = self._server_url if url is None else url
        headers = {'Content-Type': 'application/json'}
        body = self._make_request_body(method, params=params)

        log.debug("Sending POST request to '%s' for method '%s'", url, method)
        try:
            async with aiohttp.request('POST', url, headers=headers, json=body) as response:
                if not response.status < 400:
                    raise aiohttp.http.HttpProcessingError(
                        code=response.status,
                        message=response.reason,
                        headers=response.headers
                    )
                return await response.json()
        except aiohttp.ClientConnectionError as error:
            self._is_connected = False
            log.error("Failed to connect to '%s': %s", url, error)
