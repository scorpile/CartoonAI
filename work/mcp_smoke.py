"""Smoke test of the MCP server over stdio: initialize, tools/list and one tools/call (list_projects).

    python work/mcp_smoke.py [projects-dir]
"""
import asyncio
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO = Path(__file__).resolve().parents[1]


async def main(projects):
    params = StdioServerParameters(command=sys.executable, args=['-m', 'celstudio.mcp', '--projects', projects], cwd=str(REPO))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print('server:', (getattr(init, 'server_info', None) or init.serverInfo).name)
            tools = await session.list_tools()
            print('tools:', ', '.join(t.name for t in tools.tools))
            result = await session.call_tool('list_projects', {})
            print('list_projects ->', result.content[0].text[:300])
            result = await session.call_tool('list_verbs', {'kind': 'shot'})
            print('list_verbs(shot) isError =', (getattr(result, 'is_error', None) if hasattr(result, 'is_error') else result.isError))
            result = await session.call_tool('render_frame', {'project_id': 'taller-v3', 'shot_id': 's05', 'time': 1.0, 'width': 480})
            print('render_frame ->', result.content[0].type, getattr(result.content[0], 'mime_type', None) or result.content[0].mimeType)
            result = await session.call_tool('get_script', {'project_id': '../escape'})
            print('traversal rejected:', (getattr(result, 'is_error', None) if hasattr(result, 'is_error') else result.isError), '-', result.content[0].text[:80])


if __name__ == '__main__':
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else str(REPO/'projects')))
