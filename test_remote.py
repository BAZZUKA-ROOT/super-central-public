import asyncio,json
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
async def main():
 async with streamablehttp_client('https://super-central-public.onrender.com/mcp',timeout=20) as (read,write,_):
  async with ClientSession(read,write) as s:
   init=await s.initialize()
   tools=await s.list_tools()
   r=await s.call_tool('central_package_details',{'package':'mcp','registry':'pypi'})
   print(json.dumps({'server':init.serverInfo.name,'tools':[x.name for x in tools.tools],'call_is_error':r.isError,'result_excerpt':str(r.structuredContent or r.content)[:180]},ensure_ascii=False))
asyncio.run(main())