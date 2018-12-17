import requests
import datetime
from typing import Union
import logging
from lbrynet.extras.daemon.comments.exceptions import GenericServerError
from lbrynet.extras.daemon.comments.exceptions import MetadataExceptions
from lbrynet.extras.daemon.comments.exceptions import MetadataServerException
from lbrynet.extras.daemon.comments.exceptions import InvalidParamsError
from lbrynet.extras.daemon.comments.exceptions import InvalidClaimUriError
from lbrynet.extras.daemon.comments.exceptions import InternalMetadataServerError
from lbrynet.extras.daemon.comments.exceptions import UnknownMetadataServerError


log = logging.getLogger(__name__)


class MetadataServer:
    """ We refer to the server that hosts all the comment data
        and other good stuff as being the 'MetadataServer'. We use terminology
        such as "claim data", but what we are in fact referring to is
        the metadata that goes alongside the claims. Said metadata comprises
        things such as likes or dislikes, and more importantly,
        the comments.
    """
    _request_id: int = 0
    _headers = {'Content-Type': 'application/json'}

    def __init__(self, server_url: str = None, **kwargs):
        """
        :param server_url: Location of the server. Note that in the future
          this will be multiple, however for now it's just the one.
        """
        self._server_url: str = server_url
        self._server_info: dict = {'last_updated': datetime.datetime.now(), 'status': None}
        self._is_connected: bool = self.update_server_status()

    @property
    def headers(self):
        return self.headers

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @classmethod
    def request_id(cls) -> int:
        return cls._request_id

    @classmethod
    def _make_request_body(cls, method: str, params: dict = None) -> dict:
        """ Creates a body for an HTTP request to the MetadataServer as
          documented. This method increments the request ID of the entire
          class after it generates the body.

        :param method: The API method to call from the server
        :param params: The extra parameters for said method. If the server
          doesn't need them, then they don't get used
        :return: The body of the request
        """
        body = {
            'jsonrpc': '2.0',
            'id': cls._request_id,
            'method': method,
        }
        if params is not None:
            body['params'] = params
        cls._request_id += 1
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
        return self._server_info['status']

    def update_server_status(self) -> bool:
        """ Tries to get the server's current status
        :return: True if the request succeeded
        """
        response = self.make_request('status')
        self._server_info['last_updated'] = datetime.datetime.now()
        if response is None:
            return False
        self._server_info['status'] = None if 'error' in response else response['result']
        return True

    def make_request(self, method: str, params: dict = None,
                     url: str = None, **kwargs) -> Union[dict, None]:
        """ Asynchronously makes a request to the metadata server using the
        incremented ID, as well as the given method and parameters.

        Note - The API's methods and parameters are documented online at [https://ocornoc.github.io/lbry-comments]

        :param url: URL of the specific server the request will be made to
        :param method: API method to call from the comments server.
        :param params: Parameters for the given method.
        :raises InternalMetadataServerError: if something internally breaks
        :raises InvalidParamsError: if the parameters don't match the server
        :raises InvalidClaimUriError: if the wrong URI is passed in
        :raises UnknownMetadataServerError: if we hit a snag and don't know what happened
        :raises GenericServerError: if we snag a generic JSON-RPC error that
          wasn't documented by the API but is in the standard
        :return: A `dict` of the JSON response. If the request was normal then
          it will contain a 'result' field, and 'error' if otherwise
        """
        url = self._server_url if url is None else url
        headers, body = self._headers, self._make_request_body(method, params=params)

        with requests.Session() as sesh:
            try:
                log.debug("Sending POST request to '%s' for method '%s'", url, method)
                response = sesh.post(url, headers=headers, json=body)
                self._is_connected = True
            except requests.exceptions.ConnectionError:
                self._is_connected = False
                log.error("Failed to connect to '%s'", url)
                return None
        if response.status_code != 200:
            log.error("Got HTTP Error Code '%i' when connecting to '%s'",
                      response.status_code, url)
            raise requests.HTTPError()
        result = response.json()
        if 'error' in result:  # JSON-RPC errors aren't critical since HTTP status is 200
            code = result['error']['code']
            log.warning("Error from message server '%s', code %i", url, code)
            raise MetadataExceptions.get(code, GenericServerError)(result=result)

        return result


class ClaimMetadataAPI:

    def __init__(self, url: str, **kwargs):
        self.url = url
        self._server = MetadataServer(url)
        self.username = kwargs.get("username", "Tester")

    def ping(self) -> dict:
        return self._server.make_request("ping")['result']

    def get_claim_data(self, uri: str) -> dict:
        """ Returns the data associated with a claim.
        :param uri: A string containing a full-length permanent LBRY claim URI.
        :return:
        """
        try:
            claim_data = self._server.make_request("get_claim_data",
                                                   {"uri": uri})
        except InvalidClaimUriError as error:
            claim_data = error.response


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
    async def make_request(cls, url, method: str, params: dict = None):
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