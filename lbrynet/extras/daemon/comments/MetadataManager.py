import logging
from lbrynet.extras.daemon.comments.MetadataAPI import *
from lbrynet.extras.daemon.comments.exceptions import *

log = logging.getLogger(__name__)


class MetadataManager:
    
    def __init__(self, server_url: str, username: str):
        self.metadata_api = CommentsAPI(username=username, url=server_url)
    
    async def setup(self):
        await self.metadata_api._server.update_server_status()
        