import httpx


async def forward_ohttp_request(
        client: httpx.AsyncClient,
        target_url: str,
        payload: bytes,
        timeout: float,
) -> httpx.Response:
    """
    Forwards an encapsulated binary OHTTP request to the upstream storage node.
    Per RFC 9458, all client-identifying headers are stripped; only the binary payload
    and appropriate Content-Type are transmitted.
    """
    return await client.post(
        url=target_url,
        content=payload,
        headers={"content-type": "message/ohttp-req"},
        timeout=timeout,
    )
