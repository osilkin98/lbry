import logging

import aiohttp

from lbrynet.extras.daemon.comments.CommentClient import MetadataClient
from lbrynet.extras.daemon.comments.exceptions import MetadataExceptions, GenericServerError

log = logging.getLogger(__name__)


class CommentsAPI:
    def __init__(self, username: str = "A Cool LBRYian", url: str = None):
        self.url = url
        self.server = MetadataClient(self.url)
        self.username = username

    async def _call_api(self, method: str, **params) -> any:
        # This should hopefully prevent the malformed URI error
        if 'uri' in params and not params['uri'].startswith('lbry://'):
            params['uri'] = 'lbry://' + params['uri']

        if 'message' in params:
            params['message'] = params['message'].strip()
            if not 1 < len(params['message']) < 65536:
                raise ValueError("Message Body must be at most 65535 characters, "
                                 + "and at least 2 characters after stripping the"
                                 + " whitespace")
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

    @property
    def username(self) -> str:
        return self._username

    @username.setter
    def username(self, new_name: str) -> None:
        if not 2 <= len(new_name.strip()) < 128:
            raise ValueError("Username length must be at least 2 below 128")
        self._username = new_name.strip()

    @staticmethod
    def rename_key(data: dict, old: str, new: str, default: any = None) -> None:
        data[new] = data.get(old, default)
        if old in data:
            del data[old]

    @classmethod
    def correct_comment(cls, comment_data: dict) -> None:
        cls.rename_key(comment_data, 'comm_index', 'id')
        cls.rename_key(comment_data, 'poster_name', 'author')
        cls.rename_key(comment_data, 'message', 'body')
        cls.rename_key(comment_data, 'post_time', 'time_created')
        cls.rename_key(comment_data, 'parent_com', 'parent_index')

    async def ping(self) -> str:
        return await self._call_api('ping')

    async def get_claim_comments(self, uri: str) -> list:
        comments: list = await self._call_api('get_claim_comments', **{'uri': uri})
        if comments is not None:
            for comment in comments:
                self.correct_comment(comment)
        return comments

    async def create_comment(self, uri: str, message: str) -> int:
        return await self._call_api('comment', **{
            'uri': uri,
            'poster': self._username,
            'message': message
        })

    async def reply_to_comment(self, comment_id: int, message: str) -> int:
        return await self._call_api('reply_to_comment', **{
            'parent_id': comment_id,
            'poster': self._username,
            'message': message
        })

    async def get_comment(self, comment_id: int) -> dict:
        response = await self._call_api('get_comment_data', **{'comm_index': comment_id})
        if response is not None:
            self.correct_comment(response)
        return response

    async def _get_comment_reply_id_list(self, comment_id: int) -> list:
        response = await self._call_api('get_comment_replies',
                                        **{'comm_index': comment_id})
        return response

    async def _get_comment_replies(self, id_list: list) -> list:
        return [await self.get_comment(reply_id) for reply_id in id_list]

    async def get_comment_replies(self, comment_id: int) -> list:
        reply_id_list = await self._get_comment_reply_id_list(comment_id)
        return await self._get_comment_replies(reply_id_list)

    async def build_comment_tree(self, comment_id: int) -> dict:
        parent_comment = await self.get_comment(comment_id)
        if parent_comment is not None:
            reply_stack = [parent_comment]
            while len(reply_stack) > 0:
                parent = reply_stack.pop()
                parent['replies'] = await self.get_comment_replies(parent['id'])
                reply_stack += parent['replies']
        return parent_comment
