from pydantic import BaseModel
from typing import List, Dict, Optional
import json
import os
import requests
from openai import OpenAI
from tavily import TavilyClient

from tool_prompt import convert_tools_to_description, TOOL_PROMPT

# Runtime service configuration
RUNTIME_SERVICE_URL = os.getenv("RUNTIME_SERVICE_URL", "http://sf.lti.cs.cmu.edu:8005")

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


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]
    stream: bool = True


import re
from typing import List, Dict

_TAG_RE = re.compile(r"<\|(think|tool|canvas)\|>(.*?)<\|/\1\|>", re.DOTALL)


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
                elif sub_turn['role'] == 'canvas':
                    continue
                elif sub_turn['role'] == 'text':
                    new_conversation.append({'role': 'assistant', 'content': sub_turn['content']})
                elif sub_turn['role'] == 'tool':
                    new_conversation.append({'role': 'user', 'content': sub_turn['content']})
        else:
            new_conversation.append(turn)
    return new_conversation


def extract_fn_call(text):
    """
    Extract function calls from text. Returns:
    - List of function call dicts if valid format found
    - {'error': 'message'} if wrong format detected
    - None if no function call found
    """
    if not text:
        return None
    text = re.split(r'<\[[^\]]+\]>', text)[-1].strip()
    matches = list(re.finditer(r'(?m)^[ \t]*<function=([^>]+)>\s*(.*?)\s*</function>',
                               text, re.DOTALL))
    if not matches:
        return None
    
    # Check for wrong format: <param_name>value</param_name> instead of <parameter=param_name>value</parameter>
    for m in matches:
        fn_body = m.group(2)
        # Check if using correct format
        correct_params = re.findall(r'<parameter=([^>]+)>(.*?)</parameter>', fn_body, re.DOTALL)
        # Check if using wrong format (XML-style tags without 'parameter=')
        wrong_params = re.findall(r'<([a-z_][a-z0-9_]*)>(.*?)</\1>', fn_body, re.DOTALL | re.IGNORECASE)
        # Filter out any that might be legitimate tags
        wrong_params = [(name, val) for name, val in wrong_params if name.lower() not in ['function', 'parameter']]
        
        if wrong_params and not correct_params:
            # Agent used wrong format
            fn_name = m.group(1)
            wrong_param_names = [p[0] for p in wrong_params]
            return {
                'error': f"""**Tool Call Format Error**

You used the wrong format for function parameters. 

**Your format (WRONG):**
```
<function={fn_name}>
<{wrong_param_names[0]}>value</{wrong_param_names[0]}>
</function>
```

**Correct format:**
```
<function={fn_name}>
<parameter={wrong_param_names[0]}>value</parameter>
</function>
```

Please use `<parameter=PARAM_NAME>value</parameter>` format for all parameters."""
            }
    
    groups = [[matches[0]]]
    for m in matches[1:]:
        prev = groups[-1][-1]
        line_gap = text.count('\n', prev.end(), m.start())
        groups[-1].append(m) if line_gap < 4 else groups.append([m])
    last = groups[-1]
    return [
        {
            'name': m.group(1),  # <-- each call uses its *own* captured fn name
            'arguments': dict(re.findall(r'<parameter=([^>]+)>(.*?)</parameter>',
                                         m.group(2), re.DOTALL))
        }
        for m in last
    ]


class RuntimeServiceError(Exception):
    """Exception raised when runtime service is unavailable after retries."""
    pass


class TauEnv:
    """Tau environment client with automatic recovery via conversation replay."""
    
    # Retry configuration
    MAX_RETRY_TIME = 30  # Total time to retry in seconds
    RETRY_DELAY = 2  # Delay between retries in seconds

    def __init__(self, env_name='airline', task_index=None):
        self.env_name = env_name
        self.task_index = task_index
        self.runtime_id = None
        self.meta_info = None

    def _request_with_retry(self, method, url, **kwargs):
        """Make HTTP request with retry logic (30s total timeout)."""
        import time
        start_time = time.time()
        last_error = None
        attempt = 0
        
        while time.time() - start_time < self.MAX_RETRY_TIME:
            attempt += 1
            try:
                response = requests.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except requests.exceptions.ConnectionError as e:
                last_error = e
                elapsed = time.time() - start_time
                if elapsed + self.RETRY_DELAY < self.MAX_RETRY_TIME:
                    time.sleep(self.RETRY_DELAY)
                else:
                    break
            except requests.exceptions.RequestException as e:
                # Non-connection errors (like 4xx, 5xx) - don't retry
                raise
        
        raise RuntimeServiceError(
            f"Runtime service unavailable after {attempt} attempts over {int(time.time() - start_time)}s. "
            f"Last error: {last_error}"
        )

    def ping(self):
        """Check if environment exists and is responsive."""
        if not self.runtime_id:
            return {'exists': False, 'has_ping': False, 'ping_result': None, 'meta_info': None, 'message': 'No runtime_id'}
        try:
            response = self._request_with_retry(
                'POST', f"{RUNTIME_SERVICE_URL}/ping",
                json={"runtime_id": self.runtime_id}, timeout=30
            )
            result = response.json()
            if result.get('meta_info'):
                result['meta_info'] = json.loads(result['meta_info'])
            return result
        except RuntimeServiceError:
            return {'exists': False, 'has_ping': False, 'ping_result': None, 'meta_info': None, 'message': 'Runtime service unavailable'}
        except Exception as e:
            return {'exists': False, 'has_ping': False, 'ping_result': None, 'meta_info': None, 'message': f'Ping error: {str(e)}'}

    def create(self):
        """Create new runtime environment with retry."""
        params = {"env_name": self.env_name, "task_index": self.task_index}
        response = self._request_with_retry(
            'POST', f"{RUNTIME_SERVICE_URL}/create",
            json={"env_type": "tau", "params": json.dumps(params)},
            timeout=300
        )
        result = response.json()
        self.runtime_id = result['runtime_id']
        self.meta_info = json.loads(result['meta_info'])
        self.task_index = self.meta_info['task_index']
        # Update env_name from meta_info (in case it was randomly selected)
        if 'env_name' in self.meta_info:
            self.env_name = self.meta_info['env_name']
        return self.meta_info

    def _execute_step(self, fn_call: dict):
        """Execute single step with retry."""
        response = self._request_with_retry(
            'POST', f"{RUNTIME_SERVICE_URL}/step",
            json={"runtime_id": self.runtime_id, "params": json.dumps(fn_call)},
            timeout=600
        )
        return response.json()['result']

    def get_reward(self):
        """Get reward from environment with retry."""
        response = self._request_with_retry(
            'POST', f"{RUNTIME_SERVICE_URL}/reward",
            json={"runtime_id": self.runtime_id, "params": "{}"},
            timeout=30
        )
        return response.json()['reward']

    def restore(self, conversation):
        """Restore environment by replaying actions from conversation."""
        # Parse actions from conversation
        actions = []
        for msg in conversation:
            if msg['role'] == 'assistant':
                fn_calls = extract_fn_call(msg['content'])
                if fn_calls:
                    actions.extend(fn_calls)

        # Recreate environment and replay
        self.create()
        for fn_call in actions:
            try:
                self._execute_step(fn_call)
            except Exception:
                pass  # Continue replaying even if some steps fail

    def step(self, fn_call: dict, conversation=None):
        """Execute step with automatic recovery."""
        if not self.runtime_id:
            self.create()

        # Ping and restore if needed
        if not self.ping()['exists']:
            if conversation:
                self.restore(conversation)
            else:
                self.create()

        # Execute step with retry
        try:
            return self._execute_step(fn_call)
        except Exception:
            if conversation:
                self.restore(conversation)
            else:
                self.create()
            return self._execute_step(fn_call)

    def initialize(self, existing_runtime_id=None, conversation=None):
        """Initialize environment, validating existing_runtime_id or restoring from conversation.
        Only creates new runtime if existing one is invalid/missing.
        """
        # Try to use existing runtime_id if provided
        if existing_runtime_id:
            self.runtime_id = existing_runtime_id
            ping_result = self.ping()
            if ping_result['exists']:
                # Existing runtime is valid - reuse it
                self.meta_info = ping_result.get('meta_info')
                self.task_index = self.meta_info['task_index']
                # Restore env_name from meta_info
                if 'env_name' in self.meta_info:
                    self.env_name = self.meta_info['env_name']
                return  # Don't create new runtime
        
        # Runtime doesn't exist or wasn't provided - need to create/restore
        # Check if we can restore from conversation (rare case - runtime went down)
        if conversation:
            has_actions = any(
                msg['role'] == 'assistant' and extract_fn_call(msg['content'])
                for msg in conversation
            )
            if has_actions:
                self.restore(conversation)
                return  # restore() calls create() internally
        
        # No existing runtime and no actions to restore - create fresh
        self.create()

    def get_system_prompt(self):
        """Get formatted system prompt from environment meta_info."""
        if not self.meta_info:
            ping_result = self.ping()
            if ping_result['exists']:
                self.meta_info = ping_result['meta_info']
                self.task_index = self.meta_info['task_index']

        if not self.meta_info:
            return ""

        tools_info = self.meta_info.get('tools_info', [])
        wiki = self.meta_info.get('wiki', '')
        tool_description = TOOL_PROMPT.format(description=convert_tools_to_description(tools_info))
        return wiki + '\n\n' + tool_description

    def get_canvas(self):
        """Get formatted canvas from environment meta_info."""
        return f"""**Instruction:**\n\n{self.meta_info['instruction']}\n\n**You may start with:**\n\n{self.meta_info['initial_question']}

**Rules:**
- Just generate one line at a time to simulate the user's message.
- Do not give away all the instruction at once. Only provide the information that is necessary for the current step.
- Do not hallucinate information that is not provided in the instruction. For example, if the agent asks for the order id but it is not mentioned in the instruction, do not make up an order id, just say you do not remember or have it.
- If the instruction goal is satisified, generate '###STOP###' as a standalone message without anything else to end the conversation.
- Use \\reward to check the current reward.
- Do not repeat the exact instruction in the conversation. Instead, use your own words to convey the same information.
- Try to make the conversation as natural as possible, and stick to the personalities in the instruction.

**Task split:** {self.env_name}  
**Task index:** {self.task_index}  
**Runtime:** {self.runtime_id}"""



def agent_loop(conversation, cancel_event=None, meta_info="", user_id=None, mcp_servers=None, enabled_tools=None, model="Auto", env_name='airline'):
    def is_cancelled():
        return cancel_event is not None and cancel_event.is_set()

    if isinstance(conversation, str):
        conversation = [{'role': 'user', 'content': conversation}]

    # Extract runtime_id and env_name from meta_info if provided
    task_index = None
    existing_runtime_id = None
    extracted_env_name = None
    if meta_info:
        for line in meta_info.splitlines():
            if line.startswith('runtime_id:'):
                existing_runtime_id = line[len('runtime_id:'):].strip()
            if line.startswith('task_index:'):
                task_index = int(line[len('task_index:'):].strip())
            if line.startswith('env_name:'):
                extracted_env_name = line[len('env_name:'):].strip()
    
    # Use extracted env_name if found, otherwise keep default
    if extracted_env_name:
        env_name = extracted_env_name
    
    # If env_name is still default 'airline' and no existing runtime, randomly select
    if env_name == 'airline' and not existing_runtime_id:
        import random
        env_name = random.choice(['airline', 'retail'])

    tau_env = TauEnv(env_name=env_name, task_index=task_index)
    
    # Try to initialize environment with graceful error handling
    try:
        tau_env.initialize(existing_runtime_id, conversation=conversation)
    except RuntimeServiceError as e:
        yield f"⚠️ **Runtime Service Unavailable**\n\nThe tau-bench environment service is temporarily unavailable. Please try again in a moment.\n\nError: {e}"
        return
    except Exception as e:
        yield f"⚠️ **Environment Initialization Failed**\n\nCould not initialize the environment: {e}"
        return
    
    system_prompt = tau_env.get_system_prompt()
    
    # Clean conversation - remove canvas, think, etc. before sending to model
    conversation = condense_history(conversation)
    
    yield {'info': f'runtime_id: {tau_env.runtime_id}'}
    yield {'info': f'task_index: {tau_env.task_index}'}
    yield {'info': f'env_name: {tau_env.env_name}'}

    if existing_runtime_id != tau_env.runtime_id:
        yield '<|canvas|>' + tau_env.get_canvas() + '<|/canvas|>'

    # Special handling for \tau command
    if len(conversation) == 1 and conversation[0]['content'].startswith("\\tau"):
        yield "Hi there. How can I help you today?"
        return

    if conversation[-1]['content'] == '\\reward' or '###STOP###' in conversation[-1]['content']:
        try:
            reward = tau_env.get_reward()
            yield f"Reward: {reward}"
        except RuntimeServiceError as e:
            yield f"⚠️ Could not get reward - runtime service unavailable: {e}"
        except Exception as e:
            yield f"⚠️ Error getting reward: {e}"
        return

    if conversation[0]['role'] == 'system':
        chat = [{'role': 'system', 'content': system_prompt}] + conversation[1:]
    else:
        chat = [{'role': 'system', 'content': system_prompt}] + conversation

    for iteration in range(64):
        # Check for cancellation before each API call
        if is_cancelled():
            return

        response = openai_client.responses.create(
            model='gpt-5-mini',
            input=chat,
            reasoning={'summary': 'detailed', "effort": "low"}
        )

        # Check for cancellation after API call
        if is_cancelled():
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
            return

        chat.append({'role': 'assistant', 'content': answer})
        fn_call = extract_fn_call(answer)
        observation = None
        
        # Check if extract_fn_call returned a format error
        if fn_call is not None and isinstance(fn_call, dict) and 'error' in fn_call:
            # Agent used wrong tool call format - inform them of the correct format
            observation = fn_call['error']
            chat.append({'role': 'user', 'content': observation})
            yield '<|tool|>' + observation + '<|/tool|>'
            continue  # Let agent try again with correct format
        
        if fn_call is not None and isinstance(fn_call, list) and len(fn_call) > 0:
            try:
                for fn in fn_call:
                    observation = tau_env.step(fn, conversation=chat)
                yield {'info': f'runtime_id: {tau_env.runtime_id}'}
            except RuntimeServiceError as e:
                yield f"\n\n⚠️ **Runtime Service Unavailable**\n\nCould not execute tool call. The environment service is temporarily unavailable. Please try again.\n\nError: {e}"
                return
            except Exception as e:
                observation = f"Error executing tool: {e}"
        
        if observation is None:
            break
        chat.append({'role': 'user', 'content': observation})
        yield '<|tool|>' + observation + '<|/tool|>'
    return


# for chunk in agent_loop("I'm looking to book a one-way flight from New York to Seattle on May 20."):
#     print(chunk)
#     print('\n\n')


# runtime_id, meta_info = create_env()
# print(runtime_id)
# obs = env_step(runtime_id, {'name': 'search_direct_flight', 'arguments': {'origin': 'JFK', 'destination': 'SEA', 'date': '2024-05-20'}})
# print(obs)
