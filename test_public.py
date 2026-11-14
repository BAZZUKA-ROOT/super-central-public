import asyncio,json,os,urllib.request
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
PORT=os.environ.get("PORT","18766")
URL=f"http://127.0.0.1:{PORT}/mcp"

async def test():
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health",timeout=5) as r:
        assert json.load(r)["mode"]=="public-catalog-only"
    for path in ("/privacy","/terms","/support","/"):
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}",timeout=5) as r:
            assert r.status==200
    async with streamablehttp_client(URL) as (reader,writer,_):
        async with ClientSession(reader,writer) as session:
            await session.initialize()
            listed=await session.list_tools()
            expected={"central_capabilities","central_package_details",
                      "central_github_repositories","central_official_skill"}
            names={x.name for x in listed.tools}
            assert names==expected,(names,expected)
            for t in listed.tools:
                assert t.annotations.readOnlyHint is True
                assert t.annotations.destructiveHint is False
            result={}
            for name,args in [
                ("central_capabilities",{}),
                ("central_package_details",{"package":"mcp","registry":"pypi"}),
                ("central_package_details",{"package":"typescript","registry":"npm"}),
                ("central_github_repositories",{"query":"modelcontextprotocol","limit":2}),
                ("central_official_skill",{"name":"security-best-practices","source":"openai"}),
                ("central_package_details",{"package":"../etc/passwd","registry":"pypi"}),
                ("central_official_skill",{"name":"../.env","source":"openai"})
            ]:
                response=await session.call_tool(name,args)
                assert response.isError is False,(name,args)
                result[name+"_"+str(len(result))]=str(response.structuredContent or response.content)[:180]
            print(json.dumps({"http_ok":True,"privacy":True,"tools":sorted(names),
                              "calls_tested":len(result),"outcomes":result},ensure_ascii=False))
asyncio.run(test())
