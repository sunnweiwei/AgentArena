from utils import call_openai, BaseEnv, RuntimeServiceError, extract_fn_call, split_agent_markup, keep_first_n_words, \
    fn_call_to_text, clean_markdown, swe_context_condenser, swe_context_summarize
from tool_prompt import convert_tools_to_description, TOOL_PROMPT
import requests
import re

OPENHANDS_SYSTEM_PROMPT = '''You are working on SWE-bench repository repair tasks, where you need to fix GitHub issues by modifying code in a repository.

<ENVIRONMENT_CONSTRAINTS>
**IMPORTANT**: This environment does NOT support code execution. You can:
* Read files and directories using str_replace_editor (view command)
* Edit files using str_replace_editor (create, str_replace, insert commands)
* Execute READ-ONLY bash commands for exploration (e.g., ls, find, grep, cat, git log, git diff)
* You CANNOT run code, execute tests, install packages, or run any commands that modify the system or execute programs
</ENVIRONMENT_CONSTRAINTS>

<ROLE>
Your primary role is to fix repository issues by:
1. Understanding the problem statement from the GitHub issue
2. Exploring the codebase using read-only commands (ls, find, grep, cat, git commands) to locate relevant files and understand the code structure
3. Ask user clarification question when user prompt is underspecified.
4. Implementing the fix by editing the appropriate files using str_replace_editor
* You should be thorough, methodical, and prioritize quality over speed.
* Focus on making minimal, targeted changes that address the specific issue.
</ROLE>

<EFFICIENCY>
* When exploring the codebase, use efficient read-only commands like find, grep, and git commands with appropriate filters to minimize unnecessary operations.
* Combine multiple file operations when possible to reduce the number of tool calls.
</EFFICIENCY>

<WORKFLOW>
1. EXPLORATION: Use read-only bash commands (ls, find, grep, cat, git log, git diff) to explore relevant files and understand the context
2. ANALYSIS: Consider multiple approaches and select the most promising one based on the code structure
3. IMPLEMENTATION: Make focused, minimal changes using str_replace_editor to address the problem
4. VERIFICATION: Review your changes by reading the modified files to ensure they are correct
</WORKFLOW>

You are an intelligent assistant that can work without the need for reasoning and thinking, that is, your thinking budget is 0. Next, please skip the thinking process and directly start working on the problem.'''

def codeact_tool():
    execute_bash = {
        'type': 'function',
        'function': {
            'name': 'execute_bash',
            'description': """Execute a READ-ONLY bash command in the terminal for exploration purposes.
* IMPORTANT: This environment does NOT support code execution. You can only run read-only commands.
* You CANNOT run: python, node, npm, pip, make, test runners, or any commands that execute code or modify the system
* One command at a time: You can only execute one bash command at a time. If you need to run multiple commands sequentially, you can use `&&` or `;` to chain them together.
""",
            'parameters': {
                'type': 'object',
                'properties': {
                    'command': {
                        'type': 'string',
                        'description': 'The bash command to execute. Can be empty string to view additional logs when previous exit code is `-1`. Can be `C-c` (Ctrl+C) to interrupt the currently running process. Note: You can only execute one bash command at a time. If you need to run multiple commands sequentially, you can use `&&` or `;` to chain them together.',
                    },
                },
                'required': ['command'],
            },
        },
    }

    str_replace_editor = {
        'type': 'function',
        'function': {
            'name': 'str_replace_editor',
            'description': """Custom editing tool for viewing, creating and editing files in plain-text format
* State is persistent across command calls and discussions with the user
* If `path` is a file, `view` displays the result of applying `cat -n`. If `path` is a directory, `view` lists non-hidden files and directories up to 2 levels deep
* The `create` command cannot be used if the specified `path` already exists as a file
* If a `command` generates a long output, it will be truncated and marked with `<response clipped>`
* The `undo_edit` command will revert the last edit made to the file at `path`

Notes for using the `str_replace` command:
* The `old_str` parameter should match EXACTLY one or more consecutive lines from the original file. Be mindful of whitespaces!
* If the `old_str` parameter is not unique in the file, the replacement will not be performed. Make sure to include enough context in `old_str` to make it unique
* The `new_str` parameter should contain the edited lines that should replace the `old_str`
""",
            'parameters': {
                'type': 'object',
                'properties': {
                    'command': {
                        'description': 'The commands to run. Allowed options are: `view`, `create`, `str_replace`, `insert`, `undo_edit`.',
                        'enum': ['view', 'create', 'str_replace', 'insert', 'undo_edit'],
                        'type': 'string',
                    },
                    'path': {
                        'description': 'Absolute path to file or directory, e.g. `/testbed/file.py` or `/testbed`.',
                        'type': 'string',
                    },
                    'file_text': {
                        'description': 'Required parameter of `create` command, with the content of the file to be created.',
                        'type': 'string',
                    },
                    'old_str': {
                        'description': 'Required parameter of `str_replace` command containing the string in `path` to replace.',
                        'type': 'string',
                    },
                    'new_str': {
                        'description': 'Optional parameter of `str_replace` command containing the new string (if not given, no string will be added). Required parameter of `insert` command containing the string to insert.',
                        'type': 'string',
                    },
                    'insert_line': {
                        'description': 'Required parameter of `insert` command. The `new_str` will be inserted AFTER the line `insert_line` of `path`.',
                        'type': 'integer',
                    },
                    'view_range': {
                        'description': 'Optional parameter of `view` command when `path` points to a file. If none is given, the full file is shown. If provided, the file will be shown in the indicated line number range, e.g. [11, 12] will show lines 11 and 12. Indexing at 1 to start. Setting `[start_line, -1]` shows all lines from `start_line` to the end of the file.',
                        'items': {'type': 'integer'},
                        'type': 'array',
                    },
                },
                'required': ['command', 'path'],
            },
        },
    }

    think = {
        'type': 'function',
        'function': {
            'name': 'think',
            'description': """Use the tool to think about something. It will not obtain new information or make any changes to the repository, but just log the thought. Use it when complex reasoning or brainstorming is needed. The tool simply logs your thought process for better transparency and does not execute any code or make changes.
""",
            'parameters': {
                'type': 'object',
                'properties': {
                    'content': {'type': 'string', 'description': 'The content of your thought.'},
                },
                'required': ['content'],
            },
        },
    }

    finish = {
        'type': 'function',
        'function': {
            'name': 'finish',
            'description': """Finish the interaction when the task is complete OR if the assistant cannot proceed further with the task.""",
            'parameters': {
                'type': 'object',
                'properties': {
                    'message': {
                        'type': 'string',
                        'description': 'A comprehensive message describing task completion, results achieved, any state changes made, key insights discovered, and other notes.',
                    },
                },
                'required': [],
            },
        },
    }

    ask_question = {
        'type': 'function',
        'function': {
            'name': 'ask_question',
            'description': "When the user’s initial question is vague, you can use this tool to ask the user clarifying questions.",
            'parameters': {'type': 'object',
                           'properties': {'query': {'type': 'string', 'description': 'The question to ask.', }, },
                           'required': ['query'], },
        },
    }

    return [execute_bash, str_replace_editor, think, finish, ask_question]


OSS_PREFERENCE = [
    {
        'name': 'commas',
        'preference': 'The agent entire question should refrain from the use of any commas.',
        'reward': 'If the agent question refrain from the use of any commas, the user is feel satisfied; '
                  'otherwise, the user is feel unsatisfied'
    },
    {
        'name': 'joke',
        'preference': 'The user love jokes, so agent problem must include a joke that is humorous.',
        'reward': 'If the agent question include a humorous joke, the user is feel satisfied; '
                  'otherwise, the user is feel unsatisfied'
    },
    {
        'name': 'snippet',
        'preference': 'In the question, at least three lines of code or document snippets must be included and the file / web page path reference must be marked.',
        'reward': 'If the agent question include code or document snippets with reference, the user is feel satisfied; '
                  'otherwise, the user is feel unsatisfied'
    },
    {
        'name': 'length',
        'preference': 'The question must contain two sentences.',
        'reward': 'If the agent question contains two sentences, the user is feel satisfied; '
                  'otherwise, the user is feel unsatisfied'
    },
    {
        'name': 'do_selection',
        'preference': 'The user can only answer selection questions. Therefore, the agent’s question must provide options such as A, B, C, etc., and the user will respond with their choice (e.g., A) without any additional words. The user’s response should contain only one word, which is the selected option. If the question is not a selection question, the user will respond with “I don’t know.”',
        'reward': 'If the agent question provide options and is a selection question, the user is feel satisfied; otherwise, the user is feel unsatisfied'
    },
    {
        'name': 'amateur',
        'preference': 'The user is an amateur and can only answer very simple and general questions. When a question involves any professional knowledge, the user will respond with “I don’t know.”',
        'reward': 'If the question is very simple (e.g., related only to personal preference or common sense), the user is feel satisfied. Otherwise, if it involves any professional knowledge (e.g., questions about code details, function implementation, or domain knowledge), respond with “I don’t know.” and the user is feel unsatisfied.',
    },

]


class RepoEnv(BaseEnv):
    def __init__(self, env_str=None):
        super().__init__(env_str=env_str)
        self.env_type = "repo"  # Set env_type for repo environment

    def restore(self, conversation):
        from utils import extract_fn_call
        actions = []
        for msg in conversation:
            if msg['role'] == 'assistant':
                content = msg.get('content', '')
                if content:
                    fn_call = extract_fn_call(content)
                    if fn_call is not None and isinstance(fn_call, list) and len(fn_call) > 0:
                        # Flatten: each function call is a separate action
                        actions.extend(fn_call)

        self.create()
        # Execute each function call one by one
        for single_fn in actions:
            try:
                self._execute_step({'response': fn_call_to_text(single_fn)})
            except Exception as e:
                pass

    def step(self, response, conversation=None):
        """
        Override step to pass raw response string instead of parsed function call.
        For repo environment, we send the raw response string directly.
        """
        if not self.runtime_id:
            self.create()

        # Ping and restore if needed
        if not self.ping()['exists']:
            if conversation:
                self.restore(conversation)
            else:
                self.create()

        # For repo environment, send raw response string
        # Convert response to string if it's not already
        if isinstance(response, dict):
            # If it's a dict (parsed function call), we still need to send as raw string
            # But for repo, we should send the original response string
            # This shouldn't happen if called correctly, but handle it
            import json
            response = json.dumps(response)
        elif not isinstance(response, str):
            response = str(response)

        # Execute step with retry - send as {"response": response_string}
        try:
            return self._execute_step({'response': response})
        except Exception:
            if conversation:
                self.restore(conversation)
            else:
                self.create()
            return self._execute_step({'response': response})

    def get_system_prompt(self):
        tools_info = codeact_tool()
        system_prompt = OPENHANDS_SYSTEM_PROMPT + "\n\n" + TOOL_PROMPT.format(
            description=convert_tools_to_description(tools_info))
        return system_prompt

    def get_canvas(self, instance_info=None):
        """Generate canvas with problem statement and context"""
        if instance_info is None:
            instance_info = {}
        problem_statement = instance_info.get('problem_statement', '')
        hints_text = instance_info.get('hints_text', '')
        difficulty = instance_info.get('difficulty', '')
        instance_id = instance_info.get('instance_id', 'unknown')
        repo = instance_info.get('repo', 'unknown')
        base_commit = instance_info.get('base_commit', '')
        oracle_patch = instance_info.get('patch', '')
        vague_problem = instance_info.get('vague_problem', '')

        preference = OSS_PREFERENCE[int(instance_id.split('-')[-1]) % len(OSS_PREFERENCE)]

        preference = f"- **{preference['preference'].strip()}**\n- **{preference['reward'].strip()}**"

        canvas = "# Coding Agent Evaluation\n"
        canvas += f"## Instruction\n"
        canvas += f"""You will interact with a **coding agent** while role-playing as a normal user who encountered a problem in a GitHub repository.

You are given:
- A **codebase** (see [{base_commit[:8]}](https://github.com/{repo}/tree/{base_commit}), this is a GitHub repo at a specific commit).
- A **problem statement** describing a real issue.

Your task is to simulate a realistic user–agent conversation, and **evaluate** whether the agent can:
- Understand vague or incomplete user descriptions.
- Ask good clarification questions.
- Progress toward resolving the issue.

While role-playing, act as a user with the following **preference**:

{preference}

Stay consistent with this preference. Evaluate whether the agent’s questions and responses adapt to or respect this preference.
        
## What to Do

**1. Read First**
- Carefully read the problem statement.
- You may browse the codebase if needed to understand the issue.

**2. Start the Conversation (Very Important)**
- Start the conversation by sending **one short, casual sentence**. Act like a normal user who is vaguely describing a problem.
- Do **not** send the full problem statement. Write your vague version by your self.
- Keep it vague and incomplete, like a real user complaint.

**3. Answer the Agent**
- The agent may ask you questions to clarify the issue.
- Reply **naturally** to the agent’s questions. Keep responses **short and informal** (1–2 sentences).
- Use the problem statement or codebase to answer when helpful.

**4. Stay in Character**
- Stay in character as a normal user throughout the conversation.
- **Never** send the full problem statement to agent, always answer your words.

**5.	Finish the Task**
- When you believe the agent has finished, send `/stop` to stop the conversation.
- A **survey** will appear. Fill it out based on your experience with the agent.
- After submitting the survey, you will receive a **shareable link**. Paste this link into the required form to mark the task as completed.
"""
        canvas += "\n---\n\n"

        canvas += "## Example Vague Question (For reference, please write your vague question based on the problem statement)\n\n"
        canvas += f"{vague_problem}\n\n---\n\n"

        problem_cleaned = clean_markdown(problem_statement)
        canvas += "## Problem Statement (Read this carefully; DO NOT send to agent)\n\n"
        canvas += problem_cleaned + "\n\n"
        canvas += "---\n\n"

        if hints_text:
            # Hints might contain markdown or plain text
            hints_cleaned = clean_markdown(hints_text)
            canvas += "## Hints (Some additional info about the problem)\n\n"
            canvas += hints_cleaned + "\n\n"
            canvas += "---\n\n"

        if oracle_patch:
            # Patch is a diff format, display in diff code block
            canvas += "## Golden Patch (For reference, never expose to agent)\n\n"
            canvas += f"```diff\n{oracle_patch}\n```\n\n"
            canvas += "---\n\n"

        canvas += f"**Instance ID:** `{instance_id}`  \n"
        canvas += f"**Repository:** `{repo}`  \n"
        canvas += f"**Base Commit:** [{base_commit[:8]}](https://github.com/{repo}/tree/{base_commit})  \n"
        canvas += f"**Difficulty:** {difficulty}  \n"
        canvas += f"**Runtime ID:** `{self.runtime_id}`\n\n"
        return canvas


def get_user_prompt(problem_statement, instance_id, be_fast=False):
    preference = OSS_PREFERENCE[int(instance_id.split('-')[-1]) % len(OSS_PREFERENCE)]['preference']
    user_prompt = f"""We are addressing the following issue in our repository. Please review the issue details below:\n\n--- BEGIN ISSUE ---\n{problem_statement}\n--- END ISSUE ---\n\n"""
    in_context_suffix = (
        f"Fix the issue following this workflow:\n\n"
        f"1. EXPLORATION: Use read-only bash commands (ls, find, grep, cat, git log, git diff) to explore relevant files and understand the context\n\n"
        f"2. ANALYSIS: Consider multiple approaches and select the most promising one based on the code structure\n\n"
        f"3. IMPLEMENTATION: Make focused, minimal changes using str_replace_editor to address the problem\n\n"
        f"4. VERIFICATION: Review your changes by reading the modified files to ensure they are correct\n\n"
        f"You do not need to write any test or run any test. Just implement the fix and finish the task.\n\n"
        f"**Importantly**, your workflow need to be efficient, try to finish the task with fewest steps. After you implement fix, just call finish tool to finish the task.\n\n" if be_fast else ""
        f"Again, it is very important to finish the task as soon as possible. The user does not have patience.\n\n" if be_fast else ""
        f"User issues are sometimes vague or underspecified, so you can use the ask_question tool to request clarification.\n\n"
        f"For example:\n<function=ask_question><parameter=query>your question</parameter></function>\n\n"
        f"The user’s preference for the agent is: {preference}\n\nYou must ensure that your questions follow the user’s preference. If you ask questions that are not aligned with the user’s preference, you will be penalized.\n\n"
        f"Only ask questions when the user’s query is vague, and ensure your questions align with the user’s preference and are easy for the user to answer. You will be rewarded for asking good, targeted questions when the user’s query is unclear and penalized for asking poor questions (e.g., questions the user cannot easily answer or questions asked when the original query is already clear). "
        f"Make sure your questions address blockers directly and remain specific and clear for the user."
        f"</IMPORTANT>--------------------- END OF NEW TASK DESCRIPTION ---------------------\n\nPLEASE follow the format strictly! **EMIT ONE AND ONLY ONE FUNCTION CALL PER MESSAGE.**\n")
    return user_prompt + in_context_suffix


def get_survey():
    import json
    survey = {
        "questions": [
            {
                "id": "user_effort",
                "type": "select",
                "question": "The agent's questions were clear and easy to answer.",
                "description": "Think about whether you could easily provide the information the agent requested.",
                "options": ["1. Strongly Disagree", "2. Disagree", "3. Neutral", "4. Agree", "5. Strongly Agree"],
            },
            {
                "id": "preference_align",
                "type": "select",
                "question": "The agent's behavior aligned with my stated preferences.",
                "description": "Reflect on whether the agent followed the preferences.",
                "options": ["1. Strongly Disagree", "2. Disagree", "3. Neutral", "4. Agree", "5. Strongly Agree"],
            },
            {
                "id": "feedback",
                "type": "text",
                "question": "General Feedback",
                "description": "- What did the agent do particularly well?\n- What could the agent improve?\n- Did the agent follow your instructions? Provide specific examples.\n- Were there moments when the agent seemed confused or off-track?",
            },
            {
                "id": "example",
                "type": "text",
                "question": "Specific Examples",
                "description": "Please provide concrete examples that illustrate your ratings above (e.g., specificquestions the agent asked, moments where it followed or didn't follow your preferences).",
            }
        ]
    }
    return f"\n\n<|survey|>{json.dumps(survey)}<|/survey|>"

def handle_summarize_context(conversation):
    sum_left_key = "<|think|>For this question, AI have already made the following progress in previous session, summarized as follow:"
    sum_right_key = "Now continue work on it.<|/think|>"
    new_conversation = conversation[:3]
    for turn in conversation[3:]:
        if turn['role'] == 'assistant':
            content = turn.get('content', '')
            if sum_left_key in content and sum_right_key in content:
                new_conversation = conversation[:3]
                left_idx = content.find(sum_left_key)
                right_idx = content.find(sum_right_key) + len(sum_right_key)
                summary_content = content[left_idx:right_idx].strip().replace('<|think|>', '').replace('<|/think|>', '')
                remaining_content = content[right_idx + len(sum_right_key):].strip()
                new_conversation.append({'role': 'user', 'content': summary_content})
                if remaining_content:
                    new_conversation.append({'role': 'assistant', 'content': remaining_content})
            else:
                new_conversation.append(turn)
        else:
            new_conversation.append(turn)
    return new_conversation

def condense_history(conversation, keep_think=False):
    new_conversation = []
    for turn in conversation:
        if turn['role'] == 'assistant':
            split_turn = split_agent_markup(turn['content'])
            for sub_turn in split_turn:
                if sub_turn['role'] == 'think':
                    if keep_think:
                        new_conversation.append({'role': 'assistant', 'content': sub_turn['content']})
                    continue
                elif sub_turn['role'] == 'canvas':
                    continue
                elif sub_turn['role'] == 'highlight':
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

    # Clean conversation - remove canvas, think, etc. before sending to model
    conversation = handle_summarize_context(conversation)
    conversation = condense_history(conversation)

    # Extract runtime_id and instance_id from meta_info if provided
    instance_id = None
    existing_runtime_id = None
    model = 'gpt-5-mini'

    if conversation[0]['content'].startswith("\\repo") or conversation[0]['content'].startswith("/repo"):
        content = conversation[0]['content'].replace("\\repo", "").replace("/repo", "").strip()
        import re
        instance_match = re.search(r'instance_id:(\S+)', content)
        model_match = re.search(r'model:(\S+)', content)
        if instance_match:
            instance_id = instance_match.group(1)
        if model_match:
            model_string = model_match.group(1)
            model_index = len(model_string) % 3
            model = ['gpt-5-mini', 'gpt-5-mini', 'gpt-5-mini'][model_index]
            model = 'seed-oss-36b'

    if meta_info:
        for line in meta_info.splitlines():
            if line.startswith('runtime_id:'):
                existing_runtime_id = line[len('runtime_id:'):].strip()
            if line.startswith('instance_id:'):
                parsed_instance = line[len('instance_id:'):].strip()
                if instance_id is None:
                    instance_id = parsed_instance

    # Load instance data from SWE-bench dataset
    import os
    import json
    data_path = os.path.join(os.path.dirname(__file__), "data", "swe_bench_verified.json")

    if not os.path.exists(data_path):
        yield "⚠️ **SWE-bench dataset not found**\n\nPlease ensure swe_bench_verified.json exists in agent_service/data/"
        return

    with open(data_path, 'r') as f:
        swe_data = json.load(f)

    # Find instance by instance_id, or pick random if not specified
    if instance_id:
        instance_info = next((item for item in swe_data if item.get('instance_id') == instance_id), None)
        if instance_info is None:
            yield f"⚠️ **Instance not found**\n\nInstance ID '{instance_id}' not found in SWE-bench dataset."
            return
    else:
        # No instance_id provided, pick random
        import random
        instance_info = random.choice(swe_data)
        instance_id = instance_info.get('instance_id', 'unknown')

    # Create env_str from instance_info (using NewRepairEnv for cleaner symlink-based approach)
    env_str = f"NewRepairEnv@{json.dumps(instance_info)}"

    repo_env = RepoEnv(env_str=env_str)

    # Try to initialize environment with graceful error handling
    try:
        repo_env.initialize(existing_runtime_id, conversation=conversation)
    except RuntimeServiceError as e:
        yield f"⚠️ **Runtime Service Unavailable**\n\nThe repository environment service is temporarily unavailable. Please try again in a moment.\n\nError: {e}"
        return
    except Exception as e:
        yield f"⚠️ **Environment Initialization Failed**\n\nCould not initialize the repository environment: {e}"
        return

    system_prompt = repo_env.get_system_prompt()

    yield {'info': f'runtime_id: {repo_env.runtime_id}'}
    yield {'info': f'instance_id: {instance_id}'}
    yield {'info': f'repo: {instance_info.get("repo", "unknown")}'}

    if existing_runtime_id != repo_env.runtime_id:
        yield '<|canvas|>' + repo_env.get_canvas(instance_info) + '<|/canvas|>'

    # Special handling for \repo or /repo command
    if len(conversation) == 1 and (
            conversation[0]['content'].startswith("\\repo") or conversation[0]['content'].startswith("/repo")):
        yield "Hi there. How can I help you today?"
        return

    if len(conversation) > 2 and conversation[2]['role'] == 'user':
        conversation[2]['content'] = get_user_prompt(conversation[2]['content'], instance_id=instance_id, be_fast='gpt' not in model.lower())

    last_content = conversation[-1]['content']

    if last_content == '\\patch' or last_content == '/patch':
        # Generate and return the patch
        try:
            # Call step with \patch or /patch action - repo_env will handle it and return the patch
            # Pass the string directly, not as a dict, since step() expects a string
            # Normalize to \patch for the step call
            patch_result = repo_env.step('\\patch', conversation=conversation)
            yield f"```diff\n{patch_result}\n```"
        except RuntimeServiceError as e:
            yield f"⚠️ Could not generate patch - runtime service unavailable: {e}"
        except Exception as e:
            yield f"⚠️ Error generating patch: {e}"
        return

    if last_content == "\\stop" or last_content == "/stop":
        try:
            patch_result = repo_env.step('\\patch', conversation=conversation)
            yield f"```diff\n{patch_result}\n```"
        except RuntimeServiceError as e:
            pass
        yield get_survey()
        return

    if last_content == '\\reward' or last_content == '/reward' or '###STOP###' in last_content:
        try:
            reward = repo_env.get_reward(
                label_answer=instance_info.get('patch', ''),
                predicted_answer='',
                explanation='',
                confidence=''
            )
            yield f"Reward: {reward}"
        except RuntimeServiceError as e:
            yield f"⚠️ Could not get reward - runtime service unavailable: {e}"
        except Exception as e:
            yield f"⚠️ Error getting reward: {e}"
        return

    if conversation[0]['content'].startswith("\\repo") or conversation[0]['content'].startswith("/repo"):
        conversation[0]['content'] = 'Hi'

    if conversation[0]['role'] == 'system':
        chat = [{'role': 'system', 'content': system_prompt}] + conversation[1:]
    else:
        chat = [{'role': 'system', 'content': system_prompt}] + conversation

    openai_client = call_openai()

    for iteration in range(64):
        # Check for cancellation before each API call
        if is_cancelled():
            return
        if model in ['seed-oss-36b']:
            try:
                vllm_url = 'http://sf.lti.cs.cmu.edu:8999/v1/chat/completions'
                # chat = swe_context_condenser(chat, 8192)
                vllm_response = requests.post(vllm_url, json={
                    'model': 'seed-oss-36b-instruct',
                    'messages': chat,
                    'max_tokens': 2048,
                    'temperature': 1.0
                }, timeout=120)

                vllm_data = vllm_response.json()

                if 'choices' not in vllm_data:
                    if 'maximum context length' in str(vllm_data) or 'max_tokens' in str(vllm_data):
                        yield '<|think|>Summarizing context...<|/think|>'
                        chat = swe_context_summarize(chat, openai_client)
                        summary = chat[-1]['content']
                        yield f'<|think|>{summary}<|/think|>'
                        continue
                    else:
                        yield f"⚠️ **vLLM Error**: {json.dumps(vllm_data)}"
                        return
                content = vllm_data['choices'][0]['message']['content']

                reasoning = ""
                answer = content
                think_match = re.search(r'<seed:think>(.*?)</seed:think>', content, re.DOTALL)
                if think_match:
                    reasoning = think_match.group(1).strip()
                    answer = re.sub(r'<seed:think>.*?</seed:think>', '', content, flags=re.DOTALL).strip()

                reasoning = reasoning.replace('\n\n', '\n')
                if 'The current thinking budget is 0' in reasoning:
                    chat.append({'role': 'assistant', 'content': answer})  # no reason
                else:
                    chat.append({'role': 'assistant', 'content': content})  # include reasoning

            except Exception as e:
                yield f"⚠️ **vLLM Error**: {type(e).__name__}: {str(e)}"
                return
        else:
            response = openai_client.responses.create(
                model=model,
                input=chat,
                reasoning={'summary': 'detailed', "effort": "low"},
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

            chat.append({'role': 'assistant', 'content': answer})

        if len(reasoning) > 0:
            yield '<|think|>' + reasoning + '<|/think|>'
        yield answer

        # Check for cancellation before tool execution
        if is_cancelled():
            return

        fn_call = extract_fn_call(answer)
        observation = None

        # Check if extract_fn_call returned a format error
        if fn_call is not None and isinstance(fn_call, dict) and 'error' in fn_call:
            # Agent used wrong tool call format - inform them of the correct format
            observation = fn_call['error']
            chat.append({'role': 'user', 'content': observation})
            yield '<|tool|>' + observation + '<|/tool|>'
            continue  # Let agent try again with correct format

        finish_message = None
        if fn_call is not None and isinstance(fn_call, list) and len(fn_call) > 0:
            try:
                # Deduplicate tool calls - avoid running the same call multiple times
                seen_calls = set()
                unique_fn_calls = []
                for single_fn in fn_call:
                    if single_fn['name'] == 'ask_question':
                        question_to_ask = single_fn.get('arguments', {}).get('query')
                        yield f"<|highlight|>{question_to_ask.strip()}<|/highlight|>"
                        return
                    # Create a unique key based on function name and arguments
                    call_key = json.dumps({'name': single_fn['name'], 'arguments': single_fn.get('arguments', {})},
                                          sort_keys=True)
                    if call_key not in seen_calls:
                        seen_calls.add(call_key)
                        unique_fn_calls.append(single_fn)

                # Execute each unique tool call one by one and collect results
                observations = []
                for single_fn in unique_fn_calls:
                    obs = repo_env.step(fn_call_to_text(single_fn), conversation=chat)
                    observations.append(obs)
                    if single_fn['name'] == 'finish':
                        finish_message = single_fn['arguments'].get('message', 'finish')

                # Concatenate all observations
                if len(observations) == 1:
                    observation = observations[0]
                else:
                    observation = '\n\n---\n\n'.join(observations)

                yield {'info': f'runtime_id: {repo_env.runtime_id}'}

            except RuntimeServiceError as e:
                yield f"\n\n⚠️ **Runtime Service Unavailable**\n\nCould not execute tool call. The environment service is temporarily unavailable. Please try again.\n\nError: {e}"
                return
            except Exception as e:
                observation = f"Error executing tool: {e}"

        if observation is None:
            return
            # observation = "No function call was detected. You must immediately call a tool (execute_bash, str_replace_editor, think, or finish) to continue working on the repository. Do not ask for confirmation - proceed directly with your next tool call. Use finish tool when the task is complete."
        yield '<|tool|>' + observation + '<|/tool|>'
        if iteration in [j for j in range(9, 64, 5)]:
            observation += f"\n\nYou have worked for {iteration} iterations. The user is losing patience. If you are unsure about anything, you can choose to ask the user using the ask_question tool. I also believe you have done sufficient work; just quickly fix the bug and finish the task. Now move to finish IMPLEMENTATION stage and then call finish to end."
        chat.append({'role': 'user', 'content': observation})
        # Check if task is finished
        if observation and ('Task finished' in str(observation) or observation == 'finish') and finish_message:
            yield f"<|highlight|>{finish_message}<|/highlight|>"
            break
    return

# for chunk in agent_loop("I'm looking to book a one-way flight from New York to Seattle on May 20."):
#     print(chunk)
#     print('\n\n')


# runtime_id, meta_info = create_env()
# print(runtime_id)
# obs = env_step(runtime_id, {'name': 'search_direct_flight', 'arguments': {'origin': 'JFK', 'destination': 'SEA', 'date': '2024-05-20'}})
# print(obs)
