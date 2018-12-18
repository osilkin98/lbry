from collections import namedtuple
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
        return self._headers

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
            log.warning("Error from message server '%s', code %i (Request ID: %i)", url, code, body['id'])
            raise MetadataExceptions.get(code, GenericServerError)(result=result)

        return result


Comment = namedtuple(
    typename='Comment',
    field_names=(
        'comment_index', 'claim_index', 'poster_name', 'parent_index',
        'post_time', 'message', 'upvotes', 'downvotes'
    ),
    defaults=(None,) * 8
)


class ClaimMetadataAPI:

    def __init__(self, url: str = None, **kwargs):
        # Todo: This IP is temporary and should not stay here forever
        self.url = 'http://18.233.233.111:2903/api' if url is None else url
        self._server = MetadataServer(self.url)
        self.username = kwargs.get("username", "A Cool LBRYian")

    def _call_api(self, method: str, **params) -> dict:
        """ Makes a call to the API and processes the parameters

        :param method: Name of the method to call. Plain and simple
        :param params: Optional dict containing parameters to the API function
        :return: The response from the server
        """
        # This should hopefully prevent the malformed URI error
        if 'uri' in params and not params['uri'].startswith('lbry://'):
            params['uri'] = 'lbry://' + params['uri']
        try:
            return self._server.make_request(method, params=params)
        except tuple(MetadataExceptions.values()) as e:
            return e.response

    def ping(self) -> dict:
        """ Pings the server

        :return: That's a surprise ;)
        """
        return self._server.make_request("ping")

    def get_claim_data(self, uri: str) -> dict:
        """ Returns the data associated with a claim.
        :param uri: A string containing a full-length permanent LBRY claim URI. The
          URI shuold be of the form lbry://[permanent URI]
        :return: A `dict` that stores the data under the key 'result' if successful,
          or 'error' if not.
        """
        return self._call_api('get_claim_data', **{'uri': uri})

    def upvote_claim(self, uri: str, undo: bool = False) -> dict:
        """ Upvotes a claim and returns the new total amount of upvotes.

        :param uri: A string containing a full-length permanent LBRY claim URI.
        :param undo: Specify whether or not you want to undo the upvote. False by default
        :return: The new number of upvotes on that claim
        """
        return self._call_api('upvote_claim', **{'uri': uri, 'undo': undo})

    def downvote_claim(self, uri: str, undo: bool = False) -> dict:
        """ Downvotes a claim and returns the new amount of downvotes

        :param uri: A string containing a full-length permanent LBRY claim URI.
        :param undo: Specify whether or not you want to undo the downvote. False by default.
        :return: New number of downvotes on that claim
        """
        return self._call_api('downvote_claim', **{'uri': uri, 'undo': undo})

    def get_claim_uri(self, claim_index: int) -> dict:
        """ Gets the URI of a claim given its claim index.

        :param claim_index: An integer representing the index of the claim
        :return: A String containing the full-length permanent LBRY URI
          associated with the provided index. None if there is no URI associated
          with the given claim index
        """
        return self._call_api('get_claim_uri', **{'claim_index': abs(claim_index)})

    def get_claim_comments(self, uri: str) -> dict:
        """ Returns a list of all the top level comments for a given claim.
        Each list entry is a Comment objec, which has the attributes:.

        {
            'commment_index': Comment's index in the list

            'claim_index': Claim's index in the database

            'poster_name': Username of the commenter

            'parent_index': Index of the comment that this is in reply to. None if this is the top level comment

            'post_time': `int` representing the time this comment was made. Stored as UTC Epoch seconds

            'message': Actual body of the comment

            'upvotes': self-explanatory

            'downvotes': elf-explanatory
        }

        :param uri: The claim's permanent URI.
        :return: List of dicts with information about each top level comment:

        """
        response = self._call_api('get_claim_comments', **{'uri': uri})
        if 'result' in response:
            for i, comment in enumerate(response['result']):
                comment['comment_index'] = comment['comm_index']
                del comment['comm_index']
                if 'parent_com' in comment:
                    comment['parent_index'] = comment['parent_com']
                    del comment['parent_com']
                response['result'][i] = Comment(**comment)

        return response


class CommentsAPI(ClaimMetadataAPI):

    def __init__(self, username: str = "A Cool LBRYian", url: str = None, **kwargs):
        """
        :param username: Username being used when making comments
        :param url: Server URL
        :param kwargs: Anything
        """
        self.username = username
        super().__init__(url, **kwargs)

    def _call_api(self, method: str, **params) -> dict:
        """ Overrides Claim API to add common routines that are general to most
        API functions

        :param method: API Method to call from the server
        :param params: Any parameters given to the method
        :return: `dict` object containing a 'result' field if successful,
          or an 'error' field if not. Also contains an 'id' field that contains
          the ID of the specific request, and a 'jsonrpc' field, containing
          the json-rpc version number
        """
        if 'message' in params:
            params['message'] = params['message'].strip()
            if not 1 < len(params['message']) < 128:
                raise ValueError("Message Body must be at most 65535 characters, "
                                 + "and at least 2 characters after stripping the"
                                 + " whitespace")

        return super()._call_api(method, **params)


    @property
    def username(self) -> str:
        return self._username

    @username.setter
    def username(self, new_name: str):
        """

        :param new_name: New username, should be between 2 and 127 characters
          after the whitespace is stripped from either end
        :raise ValueError: If username doesn't meet the above criteria.
        """
        # TODO: Make it so one username is universal for any instances of this object
        if not 2 <= len(new_name.strip()) < 128:
            raise ValueError("Username length must be at least 2 below 128")
        self._username = new_name.strip()

    def make_comment(self, uri: str, message: str) -> dict:
        """ Creates a top-level comment and returns its ID.

        :param uri: Permanent claim for the URI.
        :param message: A string containing the body of the comment
        :raise ValueError: If length of message is less than 2 or greater than 65535
          after stripping whitespace from the start and end
        :return: A 'result' field containing the ID of the comment if succeeded,
          or an 'error' field if failed
        """
        return self._call_api('comment', **{'uri': uri,
                                            'poster': self._username,
                                            'message': message})

    def reply(self, comment_id: int, message: str) -> dict:
        """ Replies to an existing comment and returns the created comment's ID

        :param comment_id: The ID of the comment being replied to
        :param message: The body of the reply
        :return: a 'result' field containing the ID of the newly made comment,
          or an 'error' field if the method failed
        """
        return self._call_api('reply', **{'parent_id': comment_id,
                                          'poster': self._username,
                                          'message': message})

    def get_comment(self, comment_id: int) -> dict:
        """ Gets the data for a requested comment

        :param comment_id: The ID of the requested comment
        :return: The 'result' field contains a `Comment` object representing
          the comment
        """
        response = self._call_api('get_comment_data', **{'comm_index': comment_id})
        if 'result' in response and response['result'] is not None:
            response['result'] = Comment(**response['result'])
        return response

    def upvote_comment(self, comment_id: int, undo: bool = False) -> dict:
        """ Upvote a comment given its ID. If the undo flag is set to True,
        then the upvote is removed.

        :param comment_id: ID of the comment to upvote
        :param undo: Remove an upvote from the comment. Off by default
        :return: The new number of upvotes in the 'result' field, or None if
          there is no comment that matches the given ID
        """
        return self._call_api('upvote_comment', **{'comm_index': comment_id,
                                                   'undo': undo})

    def downvote_comment(self, comment_id: int, undo: bool = False) -> dict:
        """ Downvote a comment given its ID. If the undo flag is set to True,
        then the downvote is removed.

        :param comment_id: ID of the comment to downvote
        :param undo: Remove a downvote from the comment. Off by default
        :return: The new number of downvotes in the 'result' field, or None if
          there is no comment that matches the given ID
        """
        return self._call_api('downvote_comment', **{'comm_index': comment_id,
                                                     'undo': undo})

    def get_comment_replies(self, comment_id: int) -> dict:
        """ Gets all the direct replies to a comment. These replies are
          stored as Comment objects in a list within the 'result' field.

        :param comment_id: The ID of the comment we want to see replies from
        :return: a `dict` containing a list of comment objects in the 'result'.
          If there is no comment with the specified ID, then None is stored
          in 'result' instead.
        """
        response = self._call_api('get_comment_replies',
                                  **{'comm_index': comment_id})
        if 'result' in response and response['result'] is not None:
            for i, reply in enumerate(response['result']):
                response['result'][i] = Comment(**reply)
        return response

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
