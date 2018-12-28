import datetime
from json import loads as decode_json
import asyncio
from typing import Union

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

    def __init__(self, server_url: str = None,
                 session: aiohttp.ClientSession = None,
                 event_loop: asyncio.AbstractEventLoop = None, **kwargs):
        """
        :param server_url: Location of the server. Note that in the future
          this will be multiple, however for now it's just the one.
        :param session: This is the session object to be used for making
          HTTP requests to the actual server.
        :param event_loop: Async event loop to be used by the current thread.
          Defaults to the current event loop, if one exists already.
        """
        self._server_url: str = server_url
        self.server_info: dict = {'last_updated': datetime.datetime.now(), 'status': None}
        self._is_connected = None

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

        :param method: The API method to call from the server
        :param params: The extra parameters for said method. If the server
          doesn't need them, then they don't get used
        :return: The body of the request
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
    def status(self) -> Union[dict, None]:
        """ Gets information of the server

        :return: `dict` containing information about the server. `None` if
          we weren't able to communicate with server.
        """
        return self.server_info['status']

    async def update_server_status(self) -> bool:
        """ Tries to get the server's current status
        :return: True if the request succeeded
        """
        response = await self.make_request('status')
        if response is None:
            return False
        self.server_info['status'] = None if 'error' in response else response['result']
        self.server_info['last_updated'] = datetime.datetime.now()
        return True

    async def make_request(self, method: str, params: dict = None,
                           url: str = None, **kwargs) -> Union[dict, None]:
        """ Asynchronously makes a request to the metadata server using the
        incremented ID, as well as the given method and parameters.

        Note - The API's methods and parameters are documented online at [https://ocornoc.github.io/lbry-comments]

        :param url: URL of the specific server the request will be made to
        :param method: API method to call from the comments server.
        :param params: Parameters for the given method.
        :raises requests.HTTPError: If the HTTP response is anything besides 200
        :return: A `dict` of the JSON response. If the request was normal then
          it will contain a 'result' field, and 'error' if otherwise
        """
        url = self._server_url if url is None else url
        body = self._make_request_body(method, params=params)

        async with self.session as session:
            try:
                log.debug("Sending POST request to '%s' for method '%s'", url, method)
                response = await session.post(url, json=body)
                self._is_connected = True
                if not response.status < 400:
                    raise aiohttp.http.HttpProcessingError(
                        code=response.status,
                        message=response.reason,
                        headers=response.headers
                    )
                buffer = b""
                async for data, end_of_http_chunk in response.content.iter_chunks():
                    buffer += data
                    if end_of_http_chunk:
                        return decode_json(buffer.decode('utf-8'))
                        
            except aiohttp.ClientConnectionError:
                self._is_connected = False
                log.error("Failed to connect to '%s'", url)
                return None
