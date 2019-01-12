import logging
import aiohttp

log = logging.getLogger(__name__)


async def jsonrpc_post(url: str, method: str, params: dict = None) -> dict:
    headers = {'Content-Type': 'application/json'}
    body = {'jsonrpc': '2.0', 'id': 1, 'method': method}
    if params is not None:
        body['params'] = params
    log.debug("Sending POST request to '%s' for method '%s'", url, method)
    try:
        async with aiohttp.request('POST', url, headers=headers, json=body) as response:
            return await response.json()
    except aiohttp.ClientConnectionError as error:
        log.error("Failed to connect to '%s': %s", url, error)


async def get_comment(url: str, idx: int) -> dict:
    return (await jsonrpc_post(url, 'get_comment_data', {'comm_index': idx, 'better_keys': True}))['result']
