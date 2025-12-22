import re
import os
from tavily import TavilyClient
from tool_prompt import extract_fn_call
import asyncio

# Optional MCP manager import
try:
    from mcp_manager import mcp_manager
except ImportError:
    mcp_manager = None


def keep_first_n_words(text: str, n: int = 1000) -> str:
    if not text:
        return ""
    count = 0
    for m in re.finditer(r'\S+', text):
        count += 1
        if count == n:
            return text[:m.end()] + '\n[Document is truncated.]'
    return text


class ToolHandler:
    def __init__(self, mcp_tool_map=None):
        TAVILY_API_KEY = None
        try:
            key_path = os.path.join(os.path.dirname(__file__), '..', '..', 'tavilykey')
            if os.path.exists(key_path):
                with open(key_path, 'r') as f:
                    TAVILY_API_KEY = f.read().strip()
            else:
                TAVILY_API_KEY = os.getenv('TAVILY_API_KEY', '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')
        except Exception as e:
            print(f"Warning: Could not load Tavily API key: {e}")
            TAVILY_API_KEY = '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'

        print(f"Tavily API key loaded: {TAVILY_API_KEY[:10]}...")
        self.TAVILY_API_KEY = TAVILY_API_KEY
        self.visited_query = []
        self.mcp_tool_map = mcp_tool_map

    def search(self, fn):
        tavily_client = TavilyClient(api_key=self.TAVILY_API_KEY)
        query = fn['arguments'].get('query', '')
        max_results = (lambda v: int(v) if str(v).isdigit() else 10)(fn['arguments'].get('max_results', 5))
        observation = ""
        if not query:
            observation += '[Error] The "search" function requires a "query" argument.'
        else:
            if query in self.visited_query:
                return ""
            self.visited_query.append(query)
            observation += f'[Search Results for "{query}"]\n'
            serp = tavily_client.search(query, max_results=max_results)
            for i, page in enumerate(serp['results'], 1):
                observation += (
                    f"\n--- #{i}: {page['title']}---\n"
                    f"url: {page['url']}\n"
                    f"content: {page['content']}\n"
                )
            observation += "\n"
        return observation

    def extract(self, fn):
        tavily_client = TavilyClient(api_key=self.TAVILY_API_KEY)
        url = fn['arguments'].get('url', '')
        query = fn['arguments'].get('query', None)
        observation = ""
        if not url:
            observation += '[Error] The "extract" function requires a "url" argument.'
        else:
            open_pages = tavily_client.extract(urls=url, query=query)
            for page in open_pages['results']:
                page['raw_content'] = keep_first_n_words(page['raw_content'], 4096)
                observation += (
                    f"[Page Content]\n"
                    f"url: {page['url']}\n"
                    f"raw_content: {page['raw_content']}\n"
                )
            observation += "\n"
        return observation

    def mcp(self, fn):
        name = fn['function']
        observation = ""
        if mcp_manager is None:
            observation += f'[Error] MCP manager not available. Cannot call tool {name}.\n'
            return observation
        try:
            server_id, server_config = self.mcp_tool_map[name]
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                mcp_manager.call_tool(server_id, name, fn['arguments'])
            )
            loop.close()
            if result.get("isError"):
                observation += f'[Error calling MCP tool {name}]: {result.get("content", "Unknown error")}\n'
            else:
                content_parts = result.get("content", [])
                if isinstance(content_parts, list):
                    text_parts = [item.get("text", "") for item in content_parts if
                                  isinstance(item, dict) and item.get("type") == "text"]
                    result_text = "\n".join(text_parts)
                else:
                    result_text = str(content_parts)
                observation += f'[MCP Tool {name} Result]\n{result_text}\n'
        except Exception as e:
            observation += f'[Error calling MCP tool {name}]: {str(e)}\n'
        return observation

    def run_action(self, response):
        fn_call = extract_fn_call(response)
        if fn_call is None or len(fn_call) == 0:
            return None
        else:
            observation = ''
            for fn in fn_call:
                name = fn['function']
                if self.mcp_tool_map and name in self.mcp_tool_map:
                    observation += self.mcp(fn)
                elif name == 'search':
                    observation += self.search(fn)
                elif name == 'extract':
                    observation += self.extract(fn)
            return observation
