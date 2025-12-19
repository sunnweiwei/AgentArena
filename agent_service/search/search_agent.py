from pydantic import BaseModel
from typing import List, Dict, Optional
import json
import os
from openai import OpenAI
from tavily import TavilyClient

from agent_service.tools.tool_prompt import convert_tools_to_description, TOOL_PROMPT

# Load API keys
OPENAI_API_KEY = None
try:
    key_path = os.path.join(os.path.dirname(__file__), '..', '..', 'openaikey')
    if os.path.exists(key_path):
        with open(key_path, 'r') as f:
            OPENAI_API_KEY = f.read().strip()
    else:
        key_path = '/usr1/data/weiweis/chat_server/openaikey'
        if os.path.exists(key_path):
            with open(key_path, 'r') as f:
                OPENAI_API_KEY = f.read().strip()
except Exception as e:
    print(f"Warning: Could not load OpenAI API key: {e}")

openai_client = None
if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    print("OpenAI client initialized successfully")

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


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]
    stream: bool = True


import re
from typing import List, Dict


def keep_first_n_words(text: str, n: int = 1000) -> str:
    if not text:
        return ""
    count = 0
    for m in re.finditer(r'\S+', text):
        count += 1
        if count == n:
            return text[:m.end()] + '\n[Document is truncated.]'
    return text


_TAG_RE = re.compile(r"<\|(think|tool)\|>(.*?)<\|/\1\|>", re.DOTALL)


def split_agent_markup(s: str) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    last = 0
    for m in _TAG_RE.finditer(s):
        if m.start() > last:
            txt = s[last:m.start()]
            if txt:
                out.append({"role": "text", "content": txt})
        role = m.group(1)
        content = m.group(2)
        out.append({"role": role, "content": content})
        last = m.end()

    if last < len(s):
        txt = s[last:]
        if txt:
            out.append({"role": "text", "content": txt})
    merged: List[Dict[str, str]] = []
    for chunk in out:
        if merged and merged[-1]["role"] == chunk["role"]:
            merged[-1]["content"] += chunk["content"]
        else:
            merged.append(chunk)
    return merged


def condense_history(conversation):
    new_conversation = []
    for turn in conversation:
        if turn['role'] == 'assistant':
            split_turn = split_agent_markup(turn['content'])
            for sub_turn in split_turn:
                if sub_turn['role'] == 'think':
                    continue
                elif sub_turn['role'] == 'text':
                    new_conversation.append({'role': 'assistant', 'content': sub_turn['content']})
                elif sub_turn['role'] == 'tool':
                    new_conversation.append({'role': 'user', 'content': keep_first_n_words(sub_turn['content'], 256)})
        else:
            new_conversation.append(turn)
    return new_conversation


def search_tool():
    search = {
        'type': 'function',
        'function': {
            "name": "search",
            "description": "Performs a web search: supply a string 'query'. The tool retrieves the results for the query, returning their url, title, and snippet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to execute."
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "The maximum number of search results to return (default 5)."
                    }
                },
                "required": ["query"]
            }
        }
    }
    extract = {
        'type': 'function',
        'function': {
            'name': 'extract',
            'description': (
                "Extract web page content from one or more specified URLs"
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'url': {
                        'type': 'string',
                        'description': 'The URL to extract content from.',
                    },
                    'query': {
                        'type': 'string',
                        'description': 'Optional: user intent for reranking extracted content chunks. When provided, chunks are reranked based on relevance to this query.',
                    },
                },
                'required': ['url'],
            },
        },
    }
    return [search, extract]


def extract_fn_call(text):
    if not text:
        return None
    text = re.split(r'<\[[^\]]+\]>', text)[-1].strip()
    matches = list(re.finditer(r'(?m)^[ \t]*<function=([^>]+)>\s*(.*?)\s*</function>',
                               text, re.DOTALL))
    if not matches:
        return None
    groups = [[matches[0]]]
    for m in matches[1:]:
        prev = groups[-1][-1]
        line_gap = text.count('\n', prev.end(), m.start())
        groups[-1].append(m) if line_gap < 4 else groups.append([m])
    last = groups[-1]
    return [
        {
            'function': m.group(1),  # <-- each call uses its *own* captured fn name
            'arguments': dict(re.findall(r'<parameter=([^>]+)>(.*?)</parameter>',
                                         m.group(2), re.DOTALL))
        }
        for m in last
    ]


def agent_loop(conversation, cancel_event=None, meta_info=""):
    """
    Search agent loop that yields chunks as they're generated.
    Compatible with OpenAI streaming format.

    Args:
        conversation: The conversation history
        cancel_event: Optional threading.Event to signal cancellation
        meta_info: Meta information for agent context (string)
    
    Yields:
        Either a string (content chunk) or a dict with 'info' key (meta info update)
    """
    import re
    def is_cancelled():
        return cancel_event is not None and cancel_event.is_set()
    
    # Yield initial meta_info if provided
    if meta_info:
        print(f"[agent_loop] Starting with meta_info: {meta_info[:100]}...")
        # Meta info is available but we don't yield it at start, just use it as context

    if isinstance(conversation, str):
        conversation = [{'role': 'system', 'content': ''}, {'role': 'user', 'content': conversation}]

    conversation = condense_history(conversation)
    system_prompt = conversation[0]['content'] if conversation[0]['role'] == 'system' else ""
    tool_description = TOOL_PROMPT.format(description=convert_tools_to_description(search_tool()))
    system_prompt = system_prompt + '\n\nYou have access to the following functions, you can use them or not use them depend on user question.\n\n' + tool_description
    if conversation[0]['role'] == 'system':
        chat = [{'role': 'system', 'content': system_prompt}] + conversation[1:]
    else:
        chat = [{'role': 'system', 'content': system_prompt}] + conversation

    def custom_search_env_step(response):
        tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
        fn_call = extract_fn_call(response)
        visited_query = []
        if fn_call is None or len(fn_call) == 0:
            return None
        else:
            observation = ''
            for fn in fn_call:
                name = fn['function']
                if name == 'search':
                    query = fn['arguments'].get('query', '')
                    max_results = (lambda v: int(v) if str(v).isdigit() else 10)(fn['arguments'].get('max_results', 5))
                    if not query:
                        observation += '[Error] The "search" function requires a "query" argument.'
                    else:
                        if query in visited_query:
                            continue
                        visited_query.append(query)
                        observation += f'[Search Results for "{query}"]\n'
                        serp = tavily_client.search(query, max_results=max_results)
                        for i, page in enumerate(serp['results'], 1):
                            observation += (
                                f"\n--- #{i}: {page['title']}---\n"
                                f"url: {page['url']}\n"
                                f"content: {page['content']}\n"
                            )
                        observation += "\n"

                elif name == 'extract':
                    url = fn['arguments'].get('url', '')
                    query = fn['arguments'].get('query', None)
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

    for _ in range(64):
        # Check for cancellation before each API call
        if is_cancelled():
            print("[agent_loop] Cancellation detected, stopping loop")
            return

        response = openai_client.responses.create(
            model='gpt-5-mini',
            input=chat,
            reasoning={'summary': 'detailed'}
        )

        # Check for cancellation after API call
        if is_cancelled():
            print("[agent_loop] Cancellation detected after API call, stopping loop")
            return

        reasoning = ""
        answer = ""
        for item in response.output:
            if item.type == 'reasoning' and len(item.summary) > 0:
                reasoning += '\n\n' if len(reasoning) > 0 else ''
                reasoning += item.summary[0].text
            if item.type == 'message':
                answer += '\n\n' if len(answer) > 0 else ''
                answer += item.content[0].text
        reasoning = reasoning.replace('\n\n', '\n')
        if len(reasoning) > 0:
            yield '<|think|>' + reasoning + '<|/think|>'
        yield answer

        # Check for cancellation before tool execution
        if is_cancelled():
            print("[agent_loop] Cancellation detected, stopping before tool execution")
            return

        chat.append({'role': 'assistant', 'content': answer})
        observation = custom_search_env_step(answer)
        if observation is None:
            break
        chat.append({'role': 'user', 'content': observation})
        yield '<|tool|>' + observation + '<|/tool|>'
    return




