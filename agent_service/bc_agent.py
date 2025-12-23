from utils import call_openai, BaseEnv, RuntimeServiceError, extract_fn_call, condense_history
from tool_prompt import convert_tools_to_description, TOOL_PROMPT

def bc_search_tool():
    search = {
        'type': 'function',
        'function': {
            "name": "search",
            "description": "Performs a web search: supply a string 'query' and optional 'topk'. The tool retrieves the top 'topk' results (default 10) for the query, returning their docid, url, and document content (may be truncated based on token limits).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The query string for the search."
                    },
                    "topk": {
                        "type": "integer",
                        "description": "Return the top k pages.",
                    }
                },
                "required": [
                    "query"
                ]
            }
        }
    }
    open_page = {
        'type': 'function',
        'function': {
            'name': 'open_page',
            'description': (
                "Open a page by docid or URL and return the complete content. "
                "Provide either 'docid' or 'url'; if both are provided, prefer 'docid'. "
                "The docid or URL must come from prior search tool results."
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'docid': {
                        'type': 'string',
                        'description': 'Document ID from search results to resolve and fetch.',
                    },
                    'url': {
                        'type': 'string',
                        'description': 'Absolute URL from search results to fetch.',
                    },
                },
                'required': [],
            },
        },
    }
    finish = {
        'type': 'function',
        'function': {
            'name': 'finish',
            'description': """Return the final result when you have a definitive answer or cannot progress further. Provide a concise answer plus a brief, evidence-grounded explanation.""",
            'parameters': {
                'type': 'object',
                'properties': {
                    'answer': {
                        'type': 'string',
                        'description': 'A succinct, final answer.',
                    },
                    'explanation': {
                        'type': 'string',
                        'description': 'A brief explanation for your final answer. For this section only, cite evidence documents inline by placing their docids in square brackets at the end of sentences (e.g., [20]). Do not include citations anywhere else.',
                    },
                    'confidence': {
                        'type': 'string',
                        'description': 'Confidence: your confidence score between 0% and 100% for your answer',
                    },
                },
                'required': ['answer', 'explanation'],
            },
        },
    }
    return [search, open_page, finish]

class BCEnv(BaseEnv):
    def __init__(self, question, label_answer):
        super().__init__(question=question, label_answer=label_answer)

    def get_system_prompt(self):
        tools_info = bc_search_tool()
        tool_description = TOOL_PROMPT.format(description=convert_tools_to_description(tools_info))
        return tool_description

    def get_canvas(self):
        return f"""**Full Question:**\n\n{self.meta_info['question']}\n\n**Label Answer:**\n\n{self.meta_info['label_answer']}"""


def agent_loop(conversation, cancel_event=None, meta_info="", user_id=None, mcp_servers=None, enabled_tools=None,
               model="Auto"):
    def is_cancelled():
        return cancel_event is not None and cancel_event.is_set()

    if isinstance(conversation, str):
        conversation = [{'role': 'user', 'content': conversation}]

    # Clean conversation - remove canvas, think, etc. before sending to model
    conversation = condense_history(conversation)

    # Extract runtime_id and env_name from meta_info if provided
    question = None
    label_answer = None
    existing_runtime_id = None
    if meta_info:
        for line in meta_info.splitlines():
            if line.startswith('runtime_id:'):
                existing_runtime_id = line[len('runtime_id:'):].strip()
            if line.startswith('question:'):
                question = int(line[len('question:'):].strip())
            if line.startswith('env_name:'):
                label_answer = line[len('label_answer:'):].strip()

    if question is None or label_answer is None:
        import random
        env_name = random.choice(['airline', 'retail'])

    tau_env = BCEnv(question=question, label_answer=label_answer)

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

    yield {'info': f'runtime_id: {tau_env.runtime_id}'}
    yield {'info': f'task_index: {tau_env.meta_info["task_index"]}'}
    yield {'info': f'env_name: {tau_env.meta_info["env_name"]}'}

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

    openai_client = call_openai()

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
