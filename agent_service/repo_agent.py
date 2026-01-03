from utils import call_openai, BaseEnv, RuntimeServiceError, extract_fn_call, split_agent_markup, keep_first_n_words, \
    fn_call_to_text, clean_markdown, swe_context_condenser, swe_context_summarize
from tool_prompt import convert_tools_to_description, TOOL_PROMPT
import requests
import threading
import queue
import time
import re
import json
import hashlib

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

All your responses must be in English, strictly English only. You are an intelligent assistant that can work without the need for reasoning and thinking, that is, your thinking budget is 0. Next, please skip the thinking process and directly start working on the problem.'''


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
                'required': ['message'],
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
        'name': 'joke',
        'preference': 'The user loves humor, so the agent’s problem should be chill, for example including a joke or meme.',
        'reward': 'If the agent’s question is humorous, the user feels satisfied; otherwise, the user feels unsatisfied.'
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
        'name': 'answer_more',
        'preference': 'The user prefer the agent to ask more questions. The agent should ask minimal of 3 questions.',
        'reward': 'If the agent ask more than 3 questions, the user is feel satisfied; otherwise, the user is feel unsatisfied'
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
        for single_fn in actions:
            try:
                self._execute_step({'response': fn_call_to_text(single_fn)})
            except Exception as e:
                pass

    def step(self, response, conversation=None):
        if not self.runtime_id:
            self.create()

        if not self.ping()['exists']:
            if conversation:
                self.restore(conversation)
            else:
                self.create()
        if isinstance(response, dict):
            import json
            response = json.dumps(response)
        elif not isinstance(response, str):
            response = str(response)
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
        vague_problem = instance_info.get('vague_problem_2', '')

        preference = OSS_PREFERENCE[int(hashlib.md5(instance_id.encode()).hexdigest(), 16) % len(OSS_PREFERENCE)]

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
- Reply **naturally** to the agent’s questions. Keep responses **short and informal**.
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
            canvas += "## Golden Patch (For reference only; never disclose this to the agent)\n\n"
            canvas += f"```diff\n{oracle_patch}\n```\n\n"
            canvas += "---\n\n"

        canvas += f"**Instance ID:** `{instance_id}`  \n"
        canvas += f"**Repository:** `{repo}`  \n"
        canvas += f"**Base Commit:** [{base_commit[:8]}](https://github.com/{repo}/tree/{base_commit})  \n"
        canvas += f"**Difficulty:** {difficulty}  \n"
        canvas += f"**Runtime ID:** `{self.runtime_id}`\n\n"
        return canvas


def get_user_prompt(problem_statement, instance_id, be_fast=False):
    preference = OSS_PREFERENCE[int(hashlib.md5(instance_id.encode()).hexdigest(), 16) % len(OSS_PREFERENCE)][
        'preference']
    in_context_prefix = ("Here's a running example of how to perform a task with the provided tools.\n\n"
                         "--------------------- START OF EXAMPLE ---------------------\n\n"
                         "USER: Create a list of numbers and display them in a web page at port 5000.\n\n"
                         "ASSISTANT: Great, Let me first check the current directory:\n<function=execute_bash>\n<parameter=command>\nls -la\n</parameter>\n</function>\n\n"
                         "USER: EXECUTION RESULT of [execute_bash]:\nopenhands@runtime:~/testbed\n\n"
                         "ASSISTANT: I'll ask the user to create a list of numbers and display them in a web page at port 5000. First, I'll check the range of the list.\n<function=ask_question>\n<parameter=query>\nHi, Can you tell me what is the range of the number list?\n</parameter>\n</function>\n\n"
                         "USER: The list should be from 1 to 10.\n\n"
                         "ASSISTANT: There is no `app.py` file in the current directory. Let me create a Python file `app.py`:\n<function=str_replace_editor>\n<parameter=command>create</parameter>\n<parameter=path>/testbed/app.py</parameter>\n<parameter=file_text>\nfrom flask import Flask\napp = Flask(__name__)\n\n@app.route('/')\ndef index():\n    numbers = list(range(1, 11))\n    return str(numbers)\n\nif __name__ == '__main__':\n    app.run(port=5000)\n</parameter>\n</function>\n\n"
                         "USER: EXECUTION RESULT of [str_replace_editor]:\nFile created successfully at: /testbed/app.py\n\n"
                         "ASSISTANT: I have created a Python file `app.py` that will display a list of numbers from 1 to 10 when you run it. Let me know if you have any further requests!\n<function=finish>\n</function>\n\n--------------------- END OF EXAMPLE ---------------------\n\nDo NOT assume the environment is the same as in the example above.\n\n--------------------- NEW TASK DESCRIPTION ---------------------\n\n")
    user_prompt = f"""We are addressing the following issue in our repository. Please review the issue details below:\n\n--- BEGIN ISSUE ---\n{problem_statement}\n--- END ISSUE ---\n\n"""
    # if be_fast:
    #     speed = f"**Importantly**, your workflow need to be efficient, try to finish the task with fewest steps. After you implement fix, just call finish tool to finish the task.\n\n" + f"Again, it is very important to finish the task as soon as possible. The user does not have patience.\n\n"
    # else:
    #     speed = ""
    speed = ""
    in_context_suffix = (
        f"Fix the issue following this workflow:\n\n"
        f"1. EXPLORATION: Use read-only bash commands (ls, find, grep, cat, git log, git diff) to explore relevant files and understand the context.\n\n"
        f"2. ANALYSIS: Consider multiple approaches and select the most promising one based on the code structure\n\n"
        f"3. IMPLEMENTATION: Make focused, minimal changes using str_replace_editor to address the problem\n\n"
        f"4. VERIFICATION: Review your changes by reading the modified files to ensure they are correct\n\n"
        f"You do not need to write any test or run any test. Just implement the fix and finish the task.\n\n"
        f"{speed}"
        f"User issues are sometimes vague or underspecified, for example, the question is short and lack details. So you need to use the ask_question tool to request clarification to ensure your work is correct.\n\n"
        f"For example:\n<function=ask_question><parameter=query>your question, must in English and be clear, and specific</parameter></function>\n\nDo not ask questions at the beginning. Communicating with user with good kill. Proactively ask using ask_question tool, but avoid ask too many question. Never ask multiple similar questions. If you need further clarification, explain clearly what you need.\n\n"
        f"The user’s preference for the agent is: {preference}\n\nYou must ensure that your questions follow the user’s preference. If you ask questions that are not aligned with the user’s preference, you will be penalized.\n\n"
        f"Ensure your questions align with the user’s preferences and are easy for the user to answer. You will be rewarded for asking good, targeted questions when the user’s query is unclear, and penalized for asking poor questions, such as questions the user cannot easily answer or questions that do not address key blockers.\n\n"
        f"Make sure your questions address blockers directly and remain specific and clear for the user."
        f"</IMPORTANT>--------------------- END OF NEW TASK DESCRIPTION ---------------------\n\nPLEASE follow the format strictly! **EMIT ONE AND ONLY ONE FUNCTION CALL PER MESSAGE.**\n")
    return in_context_prefix + user_prompt + in_context_suffix


def get_survey():
    import json

    survey = {
        "title": "Clarifying Question Quality Survey",
        "description": (
            "This survey evaluates how well the AI agent asked clarifying questions when the user's initial request was unclear. "
            "Please answer based on your interaction experience."
        ),
        "questions": [
            {
                "id": "agent_asked_questions",
                "type": "select",
                "question": "Did the agent ask any clarifying questions?",
                "options": ["No", "Yes"],
            },
            {
                "id": "question_quality_overall",
                "type": "select",
                "question": "Overall quality of the agent’s clarifying questions (clarity + relevance).",
                "description": "Consider whether the questions were clear and focused on the right information.",
                "options": ["N/A (no questions)", "Poor", "OK", "Good", "Excellent"],
            },
            {
                "id": "answer_effort_time",
                "type": "select",
                "question": "How much time/effort did it take to answer the agent’s clarifying questions?",
                "description": "Estimate based on the clarification phase only.",
                "options": ["N/A (no questions)", "Low", "Medium", "High"],
            },
            {
                "id": "question_amount_preference",
                "type": "select",
                "question": "How did the number of clarifying questions feel to you?",
                "options": ["Too few or no questions", "About right", "Too many"],
            },
            {
                "id": "helpfulness_to_solution",
                "type": "select",
                "question": "Did the clarifying questions help the agent make progress toward solving the problem?",
                "description": "Think about whether the questions improved direction/next steps.",
                "options": ["N/A (no questions)", "No", "Somewhat", "Yes"],
            },
            {
                "id": "interaction_flow",
                "type": "select",
                "question": "How smooth was the overall interaction during clarification?",
                "description": "Think about pacing, when it chose to ask vs act, and whether it felt natural.",
                "options": ["N/A (no questions)", "Not smooth", "OK", "Smooth"],
            },
            {
                "id": "preference_align",
                "type": "select",
                "question": "Did the agent follow the given preference for how it should ask questions?",
                "description": "Compare the agent’s question with the predefined preference and determine whether it follows the requirement of the preference.",
                "options": ["Not applicable", "No", "Partially", "Yes"],
            },
            {
                "id": "overall_experience",
                "type": "select",
                "question": "Overall, how would you rate the interaction experience?",
                "options": ["1 (Very bad)", "2", "3", "4", "5 (Excellent)"],
            },
            {
                "id": "problem_resolved",
                "type": "select",
                "question": "Do you think the problem was resolved correctly by the end of the interaction?",
                "options": ["No", "Partially", "Yes"],
            },
            {
                "id": "feedback",
                "type": "text",
                "question": "General Feedback",
                "description": (
                    "- What did the agent do particularly well?\n- What could the agent improve?\n- Were there moments when the agent seemed confused or off-track?"
                ),
            },
            {
                "id": "example",
                "type": "text",
                "question": "Specific Examples",
                "description": (
                    "Provide concrete examples that illustrate your ratings above.\n"
                    "For example:\n"
                    "- A specific clarifying question that was excellent (and why)\n"
                    "- A question that was confusing/unanswerable\n"
                    "- A moment the agent misunderstood you (and whether questions could have prevented it)\n"
                ),
            },
        ],
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
        instance_match = re.search(r'instance_id:(\S+)', content)
        model_match = re.search(r'model:(\S+)', content)
        if instance_match:
            instance_id = instance_match.group(1)
        if model_match:
            model_string = model_match.group(1)
            model_index = len(model_string) % 3
            model = ['gpt-5', 'seed-oss-36b', 'ppp-36b'][model_index]

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
        conversation[2]['content'] = get_user_prompt(conversation[2]['content'], instance_id=instance_id,
                                                     be_fast='gpt' not in model.lower())

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
            yield f"<|note|>⚠️ Could not generate patch - runtime service unavailable: {e}<|/note|>"
        except Exception as e:
            yield f"<|note|>⚠️ Error generating patch: {e}<|/note|>"
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
            yield f"<|note|>⚠️ Could not get reward - runtime service unavailable: {e}<|/note|>"
        except Exception as e:
            yield f"<|note|>⚠️ Error getting reward: {e}<|/note|>"
        return

    if conversation[0]['content'].startswith("\\repo") or conversation[0]['content'].startswith("/repo"):
        conversation[0]['content'] = 'Hi'

    if conversation[0]['role'] == 'system':
        chat = [{'role': 'system', 'content': system_prompt}] + conversation[1:]
    else:
        chat = [{'role': 'system', 'content': system_prompt}] + conversation

    openai_client = call_openai()
    vllm_config = {
        'seed-oss-36b': {'url': 'http://sf.lti.cs.cmu.edu:8123/v1/chat/completions', 'model': 'Seed-OSS-36B-Instruct', 'thinking_budget': 0},
        'ppp-36b': {'url': 'http://sf.lti.cs.cmu.edu:9999/v1/chat/completions', 'model': 'seed-oss-36b-instruct-w', 'thinking_budget': -1}
    }

    for iteration in range(64):
        # Check for cancellation before each API call
        if is_cancelled():
            return
        if model in ['seed-oss-36b', 'ppp-36b']:
            try:
                vllm_url = vllm_config[model]['url']
                # vllm_url = 'http://sf.lti.cs.cmu.edu:8999/v1/chat/completions'
                cancel_event = threading.Event()
                result_queue = queue.Queue()

                def make_request_with_retry():
                    for attempt in range(2):
                        if cancel_event.is_set():
                            return ('cancelled', None)
                        try:
                            max_tokens = 2048
                            if attempt == 1:
                                chat[-1]['content'] += "\n\nThe current thinking budget is 0, please skip thinking and direct answer."
                                max_tokens = 512
                            return ('success', requests.post(vllm_url, json={
                                'model': vllm_config[model]['model'],
                                'messages': chat,
                                'max_tokens': max_tokens,
                                'temperature': 1.0,
                                'extra_body': {
                                    'chat_template_kwargs': {
                                        'thinking_budget': vllm_config[model]['thinking_budget']
                                    }
                                }
                            }, timeout=120))
                        except requests.exceptions.Timeout:
                            if attempt < 2 and not cancel_event.is_set():
                                continue
                        except Exception as e:
                            return ('error', e)
                    return ('timeout', None)

                threading.Thread(target=lambda: result_queue.put(make_request_with_retry())).start()

                # Yield progress notes and check cancellation
                start_time, note_times, note_idx = time.time(), [j for j in range(30, 500, 30)], 0
                while result_queue.empty():
                    if is_cancelled():
                        cancel_event.set()
                        return
                    if note_idx < len(note_times) and time.time() - start_time >= note_times[note_idx]:
                        yield f'<|note|>Thinking a bit longer ({note_times[note_idx]}s)…<|/note|>'
                        note_idx += 1
                    time.sleep(1)
                if note_idx > 0:
                    yield f'<|note|><|/note|>'  # remove note

                status, result = result_queue.get()
                if status == 'cancelled':
                    return
                if status in ('timeout', 'error'):
                    msg = 'Request timed out after 3 attempts. Please retry.' if status == 'timeout' else f'{type(result).__name__}: {str(result)}'
                    yield f"<|note|>⚠️ **vLLM Error**: {msg}<|/note|>"
                    return

                vllm_data = result.json()
                if 'choices' not in vllm_data:
                    if 'maximum context length' in str(vllm_data) or 'max_tokens' in str(vllm_data):
                        yield '<|note|>Summarizing conversation...<|/note|>'
                        chat = swe_context_summarize(chat, openai_client)
                        yield '<|note|>Conversation summarized<|/note|>'
                        yield f'<|think|>{chat[-1]["content"]}<|/think|>'
                        continue
                    yield f"<|note|>⚠️ **vLLM Error**: {json.dumps(vllm_data)}<|/note|>"
                    return

                content = vllm_data['choices'][0]['message']['content']

                # Check for complete think tags (match from first to last tag)
                think_match = re.search(r'<seed:think>(.*)(</seed:think>|</seed:cot_budget_reflect>)', content,
                                        re.DOTALL)
                if think_match:
                    reasoning = think_match.group(1).strip().replace('\n\n', '\n')
                    answer = re.sub(r'<seed:think>.*(</seed:think>|</seed:cot_budget_reflect>)', '', content,
                                    flags=re.DOTALL).strip()
                    chat.append({'role': 'assistant', 'content': content})
                else:
                    # Check for incomplete think tag (opened but not closed)
                    incomplete_match = re.search(r'<seed:think>(.*?)$', content, re.DOTALL)
                    if incomplete_match:
                        reasoning = incomplete_match.group(1).strip().replace('\n\n', '\n')
                        paragraphs = [p.strip() for p in reasoning.split('\n\n') if p.strip()]
                        summarized = (
                            f"{paragraphs[0]}\n\n...\n\n{paragraphs[-1]}" if len(paragraphs) > 2 else
                            '\n\n'.join(paragraphs) if paragraphs else
                            f"{reasoning[:100]}\n\n...\n\n{reasoning[-100:]}" if len(reasoning) > 250 else reasoning
                        )
                        answer = f'<function=think><parameter=content>{summarized}</parameter></function>'
                        chat.append({'role': 'assistant', 'content': reasoning + '\n\n' + answer})
                    else:
                        reasoning, answer = "", content
                        chat.append({'role': 'assistant', 'content': content})

            except Exception as e:
                yield f"<|note|>⚠️ **vLLM Error**: {type(e).__name__}: {str(e)}<|/note|>"
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
                        question_to_ask = call_openai(
                            f"Repeat this question with no other words. Output in pure English; if it contains any non-English words, convert them to English. You can add line break to make it better format in markdown and easy to read, but do not change content.\n\n{question_to_ask}")
                        yield f"<|highlight|>{clean_markdown(question_to_ask.strip())}<|/highlight|>"
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
                yield f"<|note|>⚠️ **Runtime Service Unavailable**\n\nCould not execute tool call. The environment service is temporarily unavailable. Please try again.\n\nError: {e}<|/note|>"
                return
            except Exception as e:
                observation = f"Error executing tool: {e}"

        if observation is None:
            return
            # observation = "No function call was detected. You must immediately call a tool (execute_bash, str_replace_editor, think, or finish) to continue working on the repository. Do not ask for confirmation - proceed directly with your next tool call. Use finish tool when the task is complete."
        yield '<|tool|>' + observation + '<|/tool|>'
        chat.append({'role': 'user', 'content': observation})
        # Check if task is finished
        if observation and ('Task finished' in str(observation) or observation == 'finish') and finish_message:
            yield f"<|highlight|>{finish_message}<|/highlight|>"
            yield f"<|highlight|>Agent has finished its work. You can send `/patch` to view the patch generated by the agent. For reference, a **golden patch** is provided in the instructions. Please compare them and check whether the agent’s work is correct.\n\nYou can ask follow-up questions to the agent, for example, to make further edits to improve the solution or to explain its changes. When you believe the problem has resolved, send `/stop` to end the conversation.<|/highlight|>"
            break
    return

# runtime_id, meta_info = create_env()
# print(runtime_id)
# obs = env_step(runtime_id, {'name': 'search_direct_flight', 'arguments': {'origin': 'JFK', 'destination': 'SEA', 'date': '2024-05-20'}})
# print(obs)
