import logging

import aiohttp

from lbrynet.extras.daemon.comments.CommentClient import MetadataClient
from lbrynet.extras.daemon.comments.exceptions import MetadataExceptions, GenericServerError

log = logging.getLogger(__name__)


def rename_key(data: dict, old: str, new: str, default: any = None) -> None:
    data[new] = data.get(old, default)
    if old in data:
        del data[old]


def correct_claim(claim_data: dict, uri: str) -> dict:
    if claim_data is None:
        claim_data = {
            'claim_index': -1,
            'permanent_uri': uri,
            'time_added': 0,
            'upvotes': 0,
            'downvotes': 0
        }
    else:
        rename_key(claim_data, 'lbry_perm_uri', 'permanent_uri')
        rename_key(claim_data, 'add_time', 'time_added')
    return claim_data



def correct_comment(comment_data: dict) -> None:
    rename_key(comment_data, 'comm_index', 'id')
    rename_key(comment_data, 'poster_name', 'author')
    rename_key(comment_data, 'message', 'body')
    rename_key(comment_data, 'post_time', 'time_created')
    rename_key(comment_data, 'parent_com', 'parent_index')


class ClaimMetadataAPI:
    def __init__(self, url: str = None, **kwargs):
        # Todo: This IP is temporary and should not stay here forever
        self.url = 'http://18.233.233.111:2903/api' if url is None else url
        self.server = MetadataClient(self.url)
        self.username = kwargs.get("username", "A Cool LBRYian")

    async def _call_api(self, method: str, **params) -> any:
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
            response = await self.server.make_request(method, params=params)
            if 'error' in response:
                raise MetadataExceptions.get(   # Raise the exception that
                    response['error']['code'],  # corresponds to error code
                    GenericServerError  # Default to this if none do
                )(response)

            return response['result']
        except aiohttp.http.HttpProcessingError as error:
            log.error("POST Request to %s got error code %i, reason: %s",
                      self.url, error.code, error.message)
            return None

    async def ping(self) -> str:
        """ Pings the server

        :return: That's a surprise ;)
        """
        return await self._call_api('ping')

    async def get_claim(self, uri: str) -> dict:
        """ Returns the data associated with a claim. If the Claim
        URI isn't in the database, then there is no user data that is being stored
        in the server. If this is the case, the claim index will just be -1 to
        indicate that it isn't in the database yet. This does not mean that it isn't
        on LBRY, just that there hasn't been any recorded data worth storing.

        :param uri: A string containing a full-length permanent LBRY claim URI. The
          URI shuold be of the form lbry://[permanent URI]
        :raises InvalidClaimUriError: If the URI isn't acceptable
        :return: `dict` Representing the claim's metadata.
        """
        claim_data = await self._call_api('get_claim_data', **{'uri': uri})
        return correct_claim(claim_data, uri)

    async def upvote_claim(self, uri: str, undo: bool = False) -> int:
        """ Upvotes a claim and returns the new total amount of upvotes.

        :param uri: A string containing a full-length permanent LBRY claim URI.
        :param undo: Specify whether or not you want to undo the upvote. False by default
        :return: The new number of upvotes on that claim
        """
        return await self._call_api('upvote_claim', **{'uri': uri, 'undo': undo})

    async def downvote_claim(self, uri: str, undo: bool = False) -> int:
        """ Downvotes a claim and returns the new amount of downvotes

        :param uri: A string containing a full-length permanent LBRY claim URI.
        :param undo: Specify whether or not you want to undo the downvote. False by default.
        :return: New number of downvotes on that claim
        """
        return await self._call_api('downvote_claim', **{'uri': uri, 'undo': undo})

    async def get_claim_uri(self, claim_index: int) -> str:
        """ Gets the URI of a claim given its claim index.

        :param claim_index: An integer representing the index of the claim
        :return: A String containing the full-length permanent LBRY URI
          associated with the provided index. None if there is no URI associated
          with the given claim index
        """
        return await self._call_api('get_claim_uri', **{'claim_index': abs(claim_index)})

    async def get_claim_comments(self, uri: str) -> list:
        """ Returns a list of Comment objects representing all the top level
          Comments for the given claim URI

        :param uri: The claim's permanent URI.
        :raises InvalidClaimUriError: If the URI isn't valid or acceptable
        :return: List of Comment objects, or None if the claim isn't in the
          database
        """
        comments: list = await self._call_api('get_claim_comments', **{'uri': uri})
        if comments is not None:
            for comment in comments:
                correct_comment(comment)
        return comments


class CommentsAPI(ClaimMetadataAPI):
    def __init__(self, username: str = "A Cool LBRYian", url: str = None, **kwargs):
        """
        :param username: Username being used when making comments
        :param url: Server URL
        :param kwargs: Anything
        """
        self.username = username
        super().__init__(url, username=username, **kwargs)

    async def _call_api(self, method: str, **params) -> any:
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

        return await super()._call_api(method, **params)

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

    async def make_comment(self, uri: str, message: str) -> int:
        """ Creates a top-level comment and returns its ID.

        :param uri: Permanent claim for the URI.
        :param message: A string containing the body of the comment
        :raises ValueError: If length of message is less than 2 or greater than 65535
          after stripping whitespace from the start and end
        :raises InvalidClaimUriError: If the provided URI isn't valid / acceptable
        :return: ID of the newly created comment
        """
        return await self._call_api('comment', **{
            'uri': uri,
            'poster': self._username,
            'message': message
        })

    async def reply(self, comment_id: int, message: str) -> int:
        """ Replies to an existing comment and returns the created comment's ID

        :param comment_id: The ID of the comment being replied to
        :param message: The body of the reply
        :raises ValueError: If the length of the comment isn't between
          2 and 65535
        :return: The ID of the new comment or None if the comment doesn't exist
        """
        return await self._call_api('reply', **{
            'parent_id': comment_id,
            'poster': self._username,
            'message': message
        })

    async def get_comment(self, comment_id: int) -> dict:
        """ Gets the data for a requested comment

        :param comment_id: The ID of the requested comment
        :return: Comment object if the comment exists, None otherwise
        """
        response = await self._call_api('get_comment_data', **{'comm_index': comment_id})
        if response is not None:
            correct_comment(response)
        return response

    async def upvote_comment(self, comment_id: int, undo: bool = False) -> int:
        """ Upvote a comment given its ID. If the undo flag is set to True,
        then the upvote is removed.

        :param comment_id: ID of the comment to upvote
        :param undo: Remove an upvote from the comment. Off by default
        :return: New number of upvotes on the comment, or None if
          it doesn't exist
        """
        return await self._call_api('upvote_comment', **{
            'comm_index': comment_id,
            'undo': undo
        })

    async def downvote_comment(self, comment_id: int, undo: bool = False) -> int:
        """ Downvote a comment given its ID. If the undo flag is set to True,
        then the downvote is removed.

        :param comment_id: ID of the comment to downvote
        :param undo: Remove a downvote from the comment. Off by default
        :return: New number of downvotes on that comment, or None if it
          doesn't exist
        """
        return await self._call_api('downvote_comment', **{
            'comm_index': comment_id,
            'undo': undo
        })

    async def _get_comment_reply_id_list(self, comment_id: int) -> list:
        """ Gets the IDs of all the comments that replied to the given
          comment ID and returns them as a list.

        :param comment_id: The ID of the comment we want to see replies from
        :return: List of IDs that link to comment objects. or None if
          there is no comment with that given ID
        """
        response = await self._call_api('get_comment_replies',
                                        **{'comm_index': comment_id})
        return response

    async def _get_comment_replies(self, id_list: list) -> list:
        """ Given a list of Reply IDs, this will generate a list of
        corresponding comment objects

        :param id_list: List of comment IDs
        :return: List of Comment objects with their indices corresponding to
          that of the given id_list.
        """
        return [await self.get_comment(reply_id) for reply_id in id_list]

    async def get_replies(self, comment: dict) -> list:
        """ Given a comment, return a list of replies as Comment objects

        :param comment: A `Comment` object to get replies for
        :return: List of `Comment` objects that are replying to `comment`
        """
        reply_id_list = await self._get_comment_reply_id_list(comment['id'])
        return await self._get_comment_replies(reply_id_list)
