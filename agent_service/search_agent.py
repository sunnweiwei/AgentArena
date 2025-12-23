from tool_handler import ToolHandler
from tool_prompt import convert_tools_to_description, TOOL_PROMPT, search_tool, get_mcp_tools
from prompter import CHATGPT_PROMPT, SEARCH_PROMPT
from utils import call_openai, keep_first_n_words, split_agent_markup

MODEL_MAPPING = {
    'Auto': 'gpt-5-mini',
    'GPT-5 mini': 'gpt-5-mini',
    'GPT-5 nano': 'gpt-5-nano',
    'GPT-5.2': 'gpt-5.2',
    'GPT-5 mini (Search)': 'gpt-5-mini',
    'GPT-5.2 (Search)': 'gpt-5'
}


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
                    new_conversation.append({'role': 'user', 'content': keep_first_n_words(sub_turn['content'], 1024)})
        else:
            new_conversation.append(turn)
    return new_conversation


def agent_loop(conversation, cancel_event=None, meta_info="", user_id=None, mcp_servers=None, enabled_tools=None,
               model="Auto"):
    def is_cancelled():
        return cancel_event is not None and cancel_event.is_set()

    if isinstance(conversation, str):
        conversation = [{'role': 'user', 'content': conversation}]

    conversation = condense_history(conversation)
    if conversation[0]['role'] == 'system':
        system_prompt = conversation[0]['content']
    elif 'Search' in model:
        system_prompt = SEARCH_PROMPT
    else:
        system_prompt = CHATGPT_PROMPT

    actual_model = MODEL_MAPPING.get(model, 'gpt-5-mini')
    all_tools = []
    if enabled_tools is None or enabled_tools.get("web_search", True) or 'Search' in model:
        all_tools += search_tool()
    mcp_tool_list, mcp_tool_map = get_mcp_tools(mcp_servers)
    all_tools += mcp_tool_list

    tool_handler = ToolHandler(mcp_tool_map)

    print(f"[agent_loop] Total tools available: {len(all_tools)} (including {len(mcp_tool_map)} MCP tools)")

    tool_description = TOOL_PROMPT.format(description=convert_tools_to_description(all_tools))
    system_prompt = system_prompt + '\n\nYou have access to the following functions.\n\n' + tool_description
    if conversation[0]['role'] == 'system':
        chat = [{'role': 'system', 'content': system_prompt}] + conversation[1:]
    else:
        chat = [{'role': 'system', 'content': system_prompt}] + conversation

    openai_client = call_openai()
    for _ in range(64):
        # Check for cancellation before each API call
        if is_cancelled():
            print("[agent_loop] Cancellation detected, stopping loop")
            return

        response = openai_client.responses.create(
            model=actual_model,
            input=chat,
            reasoning={'summary': 'detailed', "effort": "low"}
        )

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

        if is_cancelled():
            print("[agent_loop] Cancellation detected, stopping before tool execution")
            return

        chat.append({'role': 'assistant', 'content': answer})
        observation = tool_handler.run_action(answer)
        if observation is None:
            break
        chat.append({'role': 'user', 'content': observation})
        yield '<|tool|>' + observation + '<|/tool|>'
    return
