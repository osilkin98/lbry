import logging
import aiohttp

log = logging.getLogger(__name__)


async def jsonrpc_post(url: str, method: str, **params) -> any:
    headers = {'Content-Type': 'application/json'}
    body = {'jsonrpc': '2.0', 'id': 1, 'method': method}
    if len(params):
        body['params'] = params
    log.debug("Sending POST request to '%s' for method '%s'", url, method)
    async with aiohttp.request('POST', url, headers=headers, json=body) as response:
        json_response = await response.json()
        if 'error' in json_response:
            raise Exception(json_response['error'])
        return json_response['result']


async def jsonrpc_batch(url: str, method: str, batch: list) -> list:
    headers = {'Content-Type': 'application/json'}
    complete = []
    for part in range(0, len(batch), 50):
        body = [{'jsonrpc': '2.0', 'id': part+i, 'method': method, 'params': params}
                for i, params in enumerate(batch[part:part+50])]
        async with aiohttp.request('POST', url, headers=headers, json=body) as response:
            batch_response = await response.json()
            complete += [resp['result'] for resp in batch_response if 'result' in resp]
    return complete


async def get_comment(url: str, idx: int) -> dict:
    return await jsonrpc_post(url, 'get_comment_data', comm_index=idx, better_keys=True)


async def create_index_tree(url: str, root_id: int) -> dict:
    index_tree = dict()
    stack = [[root_id]]
    while len(stack) > 0:
        parents = stack.pop()
        batch = [{'comm_index': idx} for idx in parents]
        reply_batch = await jsonrpc_batch(url, 'get_comment_replies', batch)
        for i, replies in enumerate(reply_batch):
            if replies is not None and len(replies) > 0:
                index_tree[parents[i]] = replies
                stack.append(index_tree[parents[i]])

    return index_tree


async def populate_comment_with_replies(url: str, root: dict) -> None:
    index_tree = await create_index_tree(url, root['comment_index'])
    stack = [root]
    while len(stack) > 0:
        current = stack.pop()
        if current['comment_index'] in index_tree:
            batch = [{'comm_index': reply, 'better_keys': True}
                     for reply in index_tree[current['comment_index']]]
            current['replies'] = await jsonrpc_batch(url, 'get_comment_data', batch)
            if current['replies'] is not None:
                stack += current['replies']
