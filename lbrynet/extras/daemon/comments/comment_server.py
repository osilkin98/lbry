from collections import namedtuple
import requests
import datetime
from typing import Union, Any, NamedTuple, Iterable
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
        :raises requests.HTTPError: If the HTTP response is anything besides 200
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
        if not response.ok:
            log.error("Request [%i] got HTTP Error Code '%i' when connecting to '%s'",
                      body['id'], response.status_code, url)
            raise requests.HTTPError()
        result = response.json()
        return result


class ClaimMetadata(NamedTuple):
    """ This represents a claim entry on the comment server. Please
    don't confuse this as being an actual claim object. """

    claim_index: int
    permanent_uri: str
    time_created: int
    upvotes: int
    downvotes: int

    @classmethod
    def from_response(cls: type, claim_data: dict):
        if claim_data is None:
            return None
        return cls(
            claim_data['claim_index'],  # This ugly block is needed
            claim_data['lbry_perm_uri'],  # in order to rename the
            claim_data['add_time'],  # variable names we received from
            claim_data['upvotes'],  # the server into good ones
            claim_data['downvotes']   # that normal people can read
        )


class Comment(NamedTuple):
    comment_index: int
    claim_index: int
    author: str
    parent_index: int
    time_created: int
    body: str
    upvotes: int
    downvotes: int

    @classmethod
    def from_response(cls: type, comment_data: dict):
        if comment_data is None:
            return None
        return cls(
            comment_index=comment_data['comm_index'],
            claim_index=comment_data['claim_index'],
            author=comment_data['poster_name'],
            parent_index=comment_data.get('parent_com', None),  # parent_com might be null
            time_created=comment_data['post_time'],
            body=comment_data['message'],
            upvotes=comment_data['upvotes'],
            downvotes=comment_data['downvotes']
        )


class ClaimMetadataAPI:

    def __init__(self, url: str = None, **kwargs):
        # Todo: This IP is temporary and should not stay here forever
        self.url = 'http://18.233.233.111:2903/api' if url is None else url
        self._server = MetadataServer(self.url)
        self.username = kwargs.get("username", "A Cool LBRYian")

    def _call_api(self, method: str, **params) -> any:
        """ Makes a call to the API and processes the parameters

        :param method: Name of the method to call. Plain and simple
        :param params: Optional dict containing parameters to the API function
        :raises InternalMetadataServerError: if something internally breaks
        :raises InvalidParamsError: if the parameters don't match the server
        :raises InvalidClaimUriError: if the wrong URI is passed in
        :raises UnknownMetadataServerError: if we hit a snag and don't know what happened
        :raises GenericServerError: if we snag a generic JSON-RPC error that
          is in the standard but undocumented by the server API
        :return: The response from the server
        """
        # This should hopefully prevent the malformed URI error
        if 'uri' in params and not params['uri'].startswith('lbry://'):
            params['uri'] = 'lbry://' + params['uri']
        try:
            response = self._server.make_request(method, params=params)
            if 'error' in response:
                raise MetadataExceptions.get(   # Raise the exception that
                    response['error']['code'],  # corresponds to error code
                    GenericServerError  # Default to this if none do
                )(response)

            return response['result']
        except requests.HTTPError:
            return None

    def ping(self) -> str:
        """ Pings the server

        :return: That's a surprise ;)
        """
        return self._call_api('ping')

    def get_claim(self, uri: str) -> ClaimMetadata:
        """ Returns the data associated with a claim.
        :param uri: A string containing a full-length permanent LBRY claim URI. The
          URI shuold be of the form lbry://[permanent URI]
        :raises InvalidClaimUriError: If the URI isn't acceptable
        :return: A Claim object if successful, otherwise None
        """
        claim_data = self._call_api('get_claim_data', **{'uri': uri})
        return ClaimMetadata.from_response(claim_data)

    def upvote_claim(self, uri: str, undo: bool = False) -> int:
        """ Upvotes a claim and returns the new total amount of upvotes.

        :param uri: A string containing a full-length permanent LBRY claim URI.
        :param undo: Specify whether or not you want to undo the upvote. False by default
        :return: The new number of upvotes on that claim
        """
        return self._call_api('upvote_claim', **{'uri': uri, 'undo': undo})

    def downvote_claim(self, uri: str, undo: bool = False) -> int:
        """ Downvotes a claim and returns the new amount of downvotes

        :param uri: A string containing a full-length permanent LBRY claim URI.
        :param undo: Specify whether or not you want to undo the downvote. False by default.
        :return: New number of downvotes on that claim
        """
        return self._call_api('downvote_claim', **{'uri': uri, 'undo': undo})

    def get_claim_uri(self, claim_index: int) -> str:
        """ Gets the URI of a claim given its claim index.

        :param claim_index: An integer representing the index of the claim
        :return: A String containing the full-length permanent LBRY URI
          associated with the provided index. None if there is no URI associated
          with the given claim index
        """
        return self._call_api('get_claim_uri', **{'claim_index': abs(claim_index)})

    def get_claim_comments(self, uri: str) -> list:
        """ Returns a list of Comment objects representing all the top level
          Comments for the given claim URI

        :param uri: The claim's permanent URI.
        :raises InvalidClaimUriError: If the URI isn't valid or acceptable
        :return: List of Comment objects, or None if the claim isn't in the
          database
        """
        response: list = self._call_api('get_claim_comments', **{'uri': uri})
        if response is not None:
            for i, comment in enumerate(response):
                response[i] = Comment.from_response(comment)
        return response

# doge#b0d293791d1761707c23e93eb915a3c1300d17b5


class CommentsAPI(ClaimMetadataAPI):
    def __init__(self, username: str = "A Cool LBRYian", url: str = None, **kwargs):
        """
        :param username: Username being used when making comments
        :param url: Server URL
        :param kwargs: Anything
        """
        self.username = username
        super().__init__(url, username=username, **kwargs)

    def _call_api(self, method: str, **params) -> any:
        """ Overrides Claim API to add common routines that are general to most
        API functions

        :param method: API Method to call from the server
        :param params: Any parameters given to the method
        :raises ValueError: If 'message' is in `params` and isn't between
          2^1 and 2^16 - 1
        :return: `dict` object containing a 'result' field if successful,
          or an 'error' field if not. Also contains an 'id' field that contains
          the ID of the specific request, and a 'jsonrpc' field, containing
          the json-rpc version number
        """
        if 'message' in params:
            params['message'] = params['message'].strip()
            if not 1 < len(params['message']) < 65536:
                raise ValueError("Message Body must be at most 65535 characters, "
                                 + "and at least 2 characters after stripping the"
                                 + " whitespace")

        return super()._call_api(method, **params)


    @property
    def username(self) -> str:
        return self._username

    @username.setter
    def username(self, new_name: str) -> None:
        """

        :param new_name: New username, should be between 2 and 127 characters
          after the whitespace is stripped from either end
        :raise ValueError: If username doesn't meet the above criteria.
        """
        # TODO: Make it so one username is universal for any instances of this object
        if not 2 <= len(new_name.strip()) < 128:
            raise ValueError("Username length must be at least 2 below 128")
        self._username = new_name.strip()

    def make_comment(self, uri: str, message: str) -> int:
        """ Creates a top-level comment and returns its ID.

        :param uri: Permanent claim for the URI.
        :param message: A string containing the body of the comment
        :raises ValueError: If length of message is less than 2 or greater than 65535
          after stripping whitespace from the start and end
        :raises InvalidClaimUriError: If the provided URI isn't valid / acceptable
        :return: ID of the newly created comment
        """
        return self._call_api('comment', **{'uri': uri,
                                            'poster': self._username,
                                            'message': message})

    def reply(self, comment_id: int, message: str) -> int:
        """ Replies to an existing comment and returns the created comment's ID

        :param comment_id: The ID of the comment being replied to
        :param message: The body of the reply
        :raises ValueError: If the length of the comment isn't between
          2 and 65535
        :return: The ID of the new comment or None if the comment doesn't exist
        """
        return self._call_api('reply', **{'parent_id': comment_id,
                                          'poster': self._username,
                                          'message': message})

    def get_comment(self, comment_id: int) -> Comment:
        """ Gets the data for a requested comment

        :param comment_id: The ID of the requested comment
        :return: Comment object if the comment exists, None otherwise
        """
        response = self._call_api('get_comment_data', **{'comm_index': comment_id})
        return None if response is None else Comment.from_response(response)

    def upvote_comment(self, comment_id: int, undo: bool = False) -> int:
        """ Upvote a comment given its ID. If the undo flag is set to True,
        then the upvote is removed.

        :param comment_id: ID of the comment to upvote
        :param undo: Remove an upvote from the comment. Off by default
        :return: New number of upvotes on the comment, or None if
          it doesn't exist
        """
        return self._call_api('upvote_comment', **{'comm_index': comment_id,
                                                   'undo': undo})

    def downvote_comment(self, comment_id: int, undo: bool = False) -> int:
        """ Downvote a comment given its ID. If the undo flag is set to True,
        then the downvote is removed.

        :param comment_id: ID of the comment to downvote
        :param undo: Remove a downvote from the comment. Off by default
        :return: New number of downvotes on that comment, or None if it
          doesn't exist
        """
        return self._call_api('downvote_comment', **{'comm_index': comment_id,
                                                     'undo': undo})

    def get_comment_replies(self, comment_id: int) -> list:
        """ Gets the IDs of all the comments that replied to the given
          comment ID and returns them as a list.

        :param comment_id: The ID of the comment we want to see replies from
        :return: List of IDs that link to comment objects. or None if
          there is no comment with that given ID
        """
        response: list = self._call_api('get_comment_replies',
                                        **{'comm_index': comment_id})
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
