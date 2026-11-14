"""Testa versão pública no Render, sem arquivos/segredos locais."""
import asyncio, json
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL="https://super-central-public.onrender.com/mcp"
EXPECTED={"central_capabilities","central_package_details",
          "central_github_repositories","central_official_skill"}

async def main():
    async with streamablehttp_client(URL,timeout=25) as (read,write,_):
        async with ClientSession(read,write) as session:
            result=await session.initialize()
            listed=await session.list_tools()
            names={x.name for x in listed.tools}
            assert names==EXPECTED,(names,EXPECTED)
            for tool in listed.tools:
                assert tool.annotations.readOnlyHint
                assert not tool.annotations.destructiveHint
            calls=[
                ("central_package_details",{"package":"mcp","registry":"pypi"}),
                ("central_package_details",{"package":"typescript","registry":"npm"}),
                ("central_github_repositories",{"query":"modelcontextprotocol","limit":2}),
                ("central_official_skill",{"name":"security-best-practices","source":"openai"}),
            ]
            for name,args in calls:
                response=await session.call_tool(name,args)
                assert not response.isError, name
                result_data=response.structuredContent
                if result_data is None:
                    result_data=json.loads(response.content[0].text)
                if name=="central_package_details":
                    assert result_data["found"],(name,args,result_data)
                elif name=="central_github_repositories":
                    assert result_data["status"]=="ok" and result_data["results"],result_data
                else:
                    assert result_data["status"]=="found",result_data
            print(json.dumps({"server":result.serverInfo.name,
                              "tools":sorted(names),
                              "remote_calls_passed":len(calls),
                              "annotations":"read_only",
                              "status":"ok"},ensure_ascii=False))
asyncio.run(main())
