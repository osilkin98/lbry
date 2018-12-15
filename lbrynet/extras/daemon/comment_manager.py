import requests
import datetime
from typing import Union
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

    def __init__(self, server_url: str = None):
        """
        :param server_url: Location of the server. Note that in the future
          this will be multiple, however for now it's just the one.
        """
        self._server_url = server_url
        self._server_info = {'last_updated': datetime.datetime.now(), 'status': None}
        self._is_connected = False

    @property
    def request_id(self):
        self._request_id += 1
        return self._request_id

    @property
    def server_url(self) -> str:
        return self._server_url

    @property
    def status(self) -> Union[dict, None]:
        """ Gets information of the server

        :return: `dict` containing information about the server. `None` if
          we weren't able to communicate with server.
        """
        return self._server_info['status']

    def _update_server_status(self):
        response = self._make_request('status')
        self._server_info['last_updated'] = datetime.datetime.now()
        self._server_info['status'] = None if 'error' in response else response['result']

    def _make_request(self, method: str, params: dict = None):
        """ Asynchronously makes a request to the metadata server using the
        incremented ID, as well as the given method and parameters.

        Note - The API's methods and parameters are documented online at [https://ocornoc.github.io/lbry-comments]

        :param url: URL of the specific server the request will be amade to
        :param method: API method to call from the comments server.
        :param params: Parameters for the given method.
        :return: A `dict` of the JSON response. If the request was normal then
          it will contain a 'result' field, and 'error' if otherwise
        """
        headers = {'Content-Type': 'application/json'}
        body = {'jsonrpc': '2.0',
                'method': method,
                'id': self.request_id}

        if params is not None:
            body['params'] = params

        with requests.Session() as sesh:
            response = sesh.post(self._server_url, headers=headers, json=body)

        if response.status_code != 200:
            return {'error': {'text': response.text,
                              'status_code': response.status_code}}
        return response.json()


''' ASYNC STUFF: Let's not use this until we have the normal sync version built

class MetadataServer:
    """ We refer to the server that hosts all the comment data
        and other good stuff as being the 'MetadataServer'. We use terminology
        such as "claim data", but what we are in fact referring to is
        the metadata that goes alongside the claims. Said metadata comprises
        things such as likes or dislikes, and more importantly,
        the comments.
    """
    _request_id = 0
    _session = aiohttp.ClientSession()

    def __init__(self, server_url: str = None):
        """
        :param server_url: Location of the server. Note that in the future
          this will be multiple, however for now it's just the one.
        """
        self._server_url = server_url
        self._server_info = None

    @property
    def request_id(self):
        self._request_id += 1
        return self._request_id

    @property
    def server_url(self):
        return self._server_url

    @property
    def status(self):


    @classmethod
    async def _make_request(cls, url, method: str, params: dict = None):
        """ Asynchronously makes a request to the metadata server using the
        incremented ID, as well as the given method and parameters.

        Note - The API's methods and parameters are documented online at [https://ocornoc.github.io/lbry-comments]

        :param url: URL of the specific server the request will be amade to
        :param method: API method to call from the comments server.
        :param params: Parameters for the given method.
        :return: The response received from the server
        """
        headers = {'Content-Type': 'application/json'}
        body = {'jsonrpc': '2.0',
                'method': method,
                'id': cls.request_id}

        if params is not None:
            body['params'] = params

        return await cls._session.post(url=url, headers=headers, json=body)


async def server_status(session: aiohttp.ClientSession, url) -> dict:
    headers = {"Content-Type": "application/json"}
    body = {'jsonrpc': '2.0',
            'method': 'status',
            'id': '25'}
    async with session.post(url=url, headers=headers, json=body) as response:
        return await response.json()

async def main():
    async with aiohttp.ClientSession() as session:
        response = await server_status(session, "http://18.233.233.111:2903/api")
        print(response)
'''