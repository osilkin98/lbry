import logging
from lbrynet.extras.daemon.comments.MetadataAPI import *
from lbrynet.extras.daemon.comments.exceptions import *

log = logging.getLogger(__name__)


class MetadataManager:
    
    def __init__(self, server_url: str, username: str):
        self.comments = {}
        self.claim_metadata = {}
        self.username = username
        self._metadata_api = CommentsAPI(username=username, url=server_url)
    
    async def setup(self) -> dict:
        self._metadata_api.username = self.username
        return self._metadata_api.server.update_server_status()
    
    async def :