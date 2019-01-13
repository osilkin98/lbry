import logging
import aiohttp

log = logging.getLogger(__name__)


async def jsonrpc_post(url: str, method: str, **params) -> any:
    response = (await jsonrpc_batch(url, [{
        'jsonrpc': '2.0', 'id': 1,
        'method': method,
        'params': {**params}
    }]))[0]
    if 'error' in response:
        return response['error']
    return response['result']


async def jsonrpc_batch(url: str, calls: list, batch_size: int = 50, clean: bool = False) -> list:
    headers = {'Content-Type': 'application/json'}
    complete = []
    batch_size = max(batch_size, 50)
    for i in range(0, len(calls), batch_size):
        async with aiohttp.request('POST', url, headers=headers, json=calls[i:i+batch_size]) as response:
            complete += await response.json()
    if clean:
        complete = [body['result'] if 'result' in body else None for body in complete]
    return complete
