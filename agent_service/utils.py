import os
import re
import requests
import json
from openai import OpenAI

RUNTIME_SERVICE_URL = os.getenv("RUNTIME_SERVICE_URL", "http://sf.lti.cs.cmu.edu:8005")

def call_openai():
    # Load API keys
    OPENAI_API_KEY = None
    try:
        key_path = os.path.join(os.path.dirname(__file__), '..', '..', 'openaikey')
        if os.path.exists(key_path):
            with open(key_path, 'r') as f:
                OPENAI_API_KEY = f.read().strip()
        elif os.getenv('OPENAI_API_KEY'):
            OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
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
    return openai_client


def extract_fn_call(text):
    """
    Extract function calls from text. Returns:
    - List of function call dicts if valid format found
    - {'error': 'message'} if wrong format detected
    - None if no function call found
    
    Function name must be: <function=name>
    Parameters can be: <parameter=name>value</parameter> OR <name>value</name>
    Both parameter formats can be mixed.
    """
    if not text:
        return None
    text = re.split(r'<\[[^\]]+\]>', text)[-1].strip()

    # Only accept <function=name> format for function names
    matches = list(re.finditer(
        r'(?m)^[ \t]*<function=([^>]+)>\s*(.*?)\s*</function>',
        text,
        re.DOTALL
    ))

    if not matches:
        # Check for incomplete function call
        fn_start = re.search(r'(?m)^[ \t]*<function=([^>]+)>', text)
        if fn_start:
            fn_name = fn_start.group(1)
            
            # First check for wrong format: <parameter>value</parameter> instead of <parameter=name>value</parameter>
            wrong_param_format = re.findall(r'<parameter>([^<]*)</parameter>', text)
            if wrong_param_format:
                return {
                    'error': f"""**Tool Call Format Error**

You used `<parameter>` without specifying the parameter name. The parameter name must be in the opening tag.

**Your format (WRONG):**
```
<function={fn_name}>
<parameter>{wrong_param_format[0][:50]}...</parameter>
</function>
```

**Correct format:**
```
<function={fn_name}>
<parameter=message>{wrong_param_format[0][:50]}...</parameter>
</function>
```

Please use `<parameter=PARAM_NAME>value</parameter>` format. The parameter name (e.g., `message`, `command`, `path`) must be specified in the opening tag like `<parameter=message>`."""
                }
            
            open_params = len(re.findall(r'<parameter=[^>]+>', text))
            close_params = len(re.findall(r'</parameter>', text))
            has_close_function = bool(re.search(r'</function>', text))

            if (open_params != close_params) or (not has_close_function):
                return {
                    'error': f"""**Tool Call Format Error**

It looks like you started a tool call but didn't close one or more tags (e.g., missing `</parameter>` and/or `</function>`).

**Your format (WRONG):**
```
<function={fn_name}>
<parameter=query>...
<parameter=topk>10
```

**Correct format:**
```
<function={fn_name}>
<parameter=query>...</parameter>
<parameter=topk>10</parameter>
</function>
```

Please make sure every `<parameter=...>` has a matching `</parameter>`, and every `<function=...>` has a closing `</function>`."""
                }
        return None
    
    # Check for wrong parameter format and incomplete parameters within matched function calls
    for m in matches:
        fn_body = m.group(2)
        fn_name = m.group(1)
        
        # First check for wrong format: <parameter>value</parameter> instead of <parameter=name>value</parameter>
        wrong_param_format = re.findall(r'<parameter>([^<]*)</parameter>', fn_body)
        if wrong_param_format:
            preview = wrong_param_format[0][:50].replace('\n', ' ')
            return {
                'error': f"""**Tool Call Format Error**

You used `<parameter>` without specifying the parameter name. The parameter name must be in the opening tag.

**Your format (WRONG):**
```
<function={fn_name}>
<parameter>{preview}...</parameter>
</function>
```

**Correct format:**
```
<function={fn_name}>
<parameter=message>{preview}...</parameter>
</function>
```

Please use `<parameter=PARAM_NAME>value</parameter>` format. The parameter name (e.g., `message`, `command`, `path`) must be specified in the opening tag like `<parameter=message>`."""
            }
        
        # Check for incomplete parameters
        open_params = len(re.findall(r'<parameter=[^>]+>', fn_body))
        close_params = len(re.findall(r'</parameter>', fn_body))
        if open_params != close_params:
            return {
                'error': f"""**Tool Call Format Error**

It looks like you started a tool call but didn't close one or more parameter tags (e.g., missing `</parameter>`).

**Your format (WRONG):**
```
<function={fn_name}>
<parameter=query>...
```

**Correct format:**
```
<function={fn_name}>
<parameter=query>...</parameter>
</function>
```

Please make sure every `<parameter=...>` has a matching `</parameter>`."""
            }

    # Extract parameters - support both <parameter=name>value</parameter> and <name>value</name>
    groups = [[matches[0]]]
    for m in matches[1:]:
        prev = groups[-1][-1]
        line_gap = text.count('\n', prev.end(), m.start())
        groups[-1].append(m) if line_gap < 4 else groups.append([m])
    last = groups[-1]
    
    results = []
    for m in last:
        fn_body = m.group(2)
        fn_name = m.group(1)
        
        # Extract standard format parameters: <parameter=name>value</parameter>
        standard_params = dict(re.findall(
            r'<parameter=([^>]+)>(.*?)</parameter>',
            fn_body,
            re.DOTALL
        ))
        
        # Extract XML-style parameters: <name>value</name> (but exclude 'parameter' and 'function' tags)
        xml_params = re.findall(r'<([a-z_][a-z0-9_]*)>(.*?)</\1>', fn_body, re.DOTALL | re.IGNORECASE)
        xml_params_dict = {}
        for param_name, param_value in xml_params:
            # Skip 'parameter' and 'function' tags (these are structural, not parameters)
            if param_name.lower() not in ['parameter', 'function']:
                xml_params_dict[param_name] = param_value.strip()
        
        # Merge: standard params take precedence, then XML params
        merged_params = {**xml_params_dict, **standard_params}
        
        results.append({
            'name': fn_name,
            'arguments': merged_params
        })
    
    return results


def fn_call_to_text(fn_call) -> str:
    """
    Convert a parsed function call (or list of calls) back to text format.
    
    Args:
        fn_call: Dict with 'name' and 'arguments' keys, or list of such dicts
        
    Returns:
        String in format:
          - single: <function=name>\n<parameter=key>value</parameter>\n</function>
          - list: multiple such blocks concatenated with two newlines
    """
    # If we got a list of function calls, convert each and join
    if isinstance(fn_call, list):
        parts = [fn_call_to_text(item) for item in fn_call]
        return "\n\n".join(parts)

    if not isinstance(fn_call, dict) or 'name' not in fn_call:
        raise ValueError("fn_call must be a dict with 'name' key or a list of such dicts")
    
    fn_name = fn_call['name']
    arguments = fn_call.get('arguments', {}) or {}
    
    # Build the function call text
    lines = [f"<function={fn_name}>"]
    
    # Add parameters
    for key, value in arguments.items():
        # Convert value to string, handle None
        if value is None:
            value_str = ""
        else:
            value_str = str(value)
        lines.append(f"<parameter={key}>{value_str}</parameter>")
    
    lines.append("</function>")
    
    return "\n".join(lines)


class RuntimeServiceError(Exception):
    """Exception raised when runtime service is unavailable after retries."""
    pass


class BaseEnv:
    # Retry configuration
    MAX_RETRY_TIME = 30  # Total time to retry in seconds
    RETRY_DELAY = 2  # Delay between retries in seconds

    def __init__(self, **params):
        self.params = params
        self.runtime_id = None
        self.meta_info = None
        self.env_type = "tau"  # Default, subclasses should override

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
            return {'exists': False, 'has_ping': False, 'ping_result': None, 'meta_info': None,
                    'message': 'No runtime_id'}
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
            return {'exists': False, 'has_ping': False, 'ping_result': None, 'meta_info': None,
                    'message': 'Runtime service unavailable'}
        except Exception as e:
            return {'exists': False, 'has_ping': False, 'ping_result': None, 'meta_info': None,
                    'message': f'Ping error: {str(e)}'}

    def create(self, env_type=None):
        """Create new runtime environment with retry."""
        if env_type is None:
            env_type = self.env_type
        params = self.params
        response = self._request_with_retry(
            'POST', f"{RUNTIME_SERVICE_URL}/create",
            json={"env_type": env_type, "params": json.dumps(params)},
            timeout=300
        )
        result = response.json()
        self.runtime_id = result['runtime_id']
        self.meta_info = json.loads(result['meta_info'])
        return self.meta_info

    def _execute_step(self, fn_call: dict):
        """Execute single step with retry."""
        response = self._request_with_retry(
            'POST', f"{RUNTIME_SERVICE_URL}/step",
            json={"runtime_id": self.runtime_id, "params": json.dumps(fn_call)},
            timeout=600
        )
        return response.json()['result']

    def get_reward(self, **kwargs):
        """Get reward from environment with retry."""
        response = self._request_with_retry(
            'POST', f"{RUNTIME_SERVICE_URL}/reward",
            json={"runtime_id": self.runtime_id, "params": json.dumps(kwargs)},
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


import re
from typing import List, Dict

_TAG_RE = re.compile(r"<\|(think|tool|canvas|highlight)\|>(.*?)<\|/\1\|>", re.DOTALL)


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

def keep_first_n_words(text: str, n: int = 1000) -> str:
    if not text:
        return ""
    count = 0
    for m in re.finditer(r'\S+', text):
        count += 1
        if count == n:
            return text[:m.end()] + '\n[Document is truncated.]'
    return text

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
                elif sub_turn['role'] == 'highlight':
                    continue
                elif sub_turn['role'] == 'text':
                    new_conversation.append({'role': 'assistant', 'content': sub_turn['content']})
                elif sub_turn['role'] == 'tool':
                    new_conversation.append({'role': 'user', 'content': sub_turn['content']})
        else:
            new_conversation.append(turn)
    return new_conversation
