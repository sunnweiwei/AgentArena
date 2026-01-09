from pydantic import BaseModel
from typing import List, Dict, Optional
import json
import os
import requests
from openai import OpenAI
from utils import call_openai, BaseEnv, RuntimeServiceError, extract_fn_call, condense_history
from tool_prompt import convert_tools_to_description, TOOL_PROMPT

class TauEnv(BaseEnv):
    """Tau environment client with automatic recovery via conversation replay."""
    def __init__(self, env_name, task_index):
        super().__init__(env_name=env_name, task_index=task_index)

    def get_system_prompt(self):
        """Get formatted system prompt from environment meta_info."""
        if not self.meta_info:
            ping_result = self.ping()
            if ping_result['exists']:
                self.meta_info = ping_result['meta_info']

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

**Task split:** {self.meta_info['env_name']}  
**Task index:** {self.meta_info['task_index']}  
**Runtime:** {self.runtime_id}"""



def agent_loop(conversation, cancel_event=None, meta_info="", user_id=None, mcp_servers=None, enabled_tools=None, model="Auto"):
    def is_cancelled():
        return cancel_event is not None and cancel_event.is_set()

    if isinstance(conversation, str):
        conversation = [{'role': 'user', 'content': conversation}]

    # Clean conversation - remove canvas, think, etc. before sending to model
    conversation = condense_history(conversation)

    # Extract runtime_id and env_name from meta_info if provided
    task_index = None
    existing_runtime_id = None
    env_name = None
    if meta_info:
        for line in meta_info.splitlines():
            if line.startswith('runtime_id:'):
                existing_runtime_id = line[len('runtime_id:'):].strip()
            if line.startswith('task_index:'):
                task_index = int(line[len('task_index:'):].strip())
            if line.startswith('env_name:'):
                env_name = line[len('env_name:'):].strip()

    if env_name is None:
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
    
    yield {'info': f'runtime_id: {tau_env.runtime_id}'}
    yield {'info': f'task_index: {tau_env.meta_info["task_index"]}'}
    yield {'info': f'env_name: {tau_env.meta_info["env_name"]}'}

    if existing_runtime_id != tau_env.runtime_id:
        yield '<|canvas|>' + tau_env.get_canvas() + '<|/canvas|>'

    # Special handling for \tau or /tau command
    if len(conversation) == 1 and (conversation[0]['content'].startswith("\\tau") or conversation[0]['content'].startswith("/tau")):
        yield "Hi there. How can I help you today?"
        return

    last_content = conversation[-1]['content']
    if last_content == '\\reward' or last_content == '/reward' or '###STOP###' in last_content:
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
            model='gpt-5-2025-08-07',
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
