"""Teste de servidor público local, sem acessar informações privadas."""
import asyncio
import json
import os
import urllib.request

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

PORT = os.environ.get("PORT", "18766")
URL = f"http://127.0.0.1:{PORT}/mcp"


async def test():
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=4) as r:
        assert json.load(r)["mode"] == "public-catalog-only"
    for path in ("/privacy", "/terms", "/support", "/"):
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}", timeout=4) as r:
            assert r.status == 200
    async with streamablehttp_client(URL) as (reader, writer, _):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {x.name for x in tools.tools}
            assert names == {"central_capabilities", "central_package_details"}, names
            for x in tools.tools:
                assert x.annotations.readOnlyHint is True
                assert x.annotations.destructiveHint is False
            result = await session.call_tool("central_capabilities")
            assert result.isError is False
            result2 = await session.call_tool("central_package_details",
                                              {"package": "mcp", "registry": "pypi"})
            assert result2.isError is False
            bad = await session.call_tool("central_package_details",
                                          {"package": "../etc/passwd", "registry": "pypi"})
            assert bad.isError is False
            print(json.dumps({"http_ok": True, "privacy": True, "tools": sorted(names),
                              "pypi_query": True, "malicious_input_rejected": True},
                             ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(test())
