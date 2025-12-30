from utils import call_openai, BaseEnv, RuntimeServiceError, extract_fn_call, split_agent_markup, keep_first_n_words, fn_call_to_text
from tool_prompt import convert_tools_to_description, TOOL_PROMPT


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
3. Implementing the fix by editing the appropriate files using str_replace_editor
* You should be thorough, methodical, and prioritize quality over speed.
* Focus on making minimal, targeted changes that address the specific issue.
</ROLE>

<EFFICIENCY>
* When exploring the codebase, use efficient read-only commands like find, grep, and git commands with appropriate filters to minimize unnecessary operations.
* Combine multiple file operations when possible to reduce the number of tool calls.
</EFFICIENCY>

<FILE_OPERATIONS>
* When a user provides a file path, do NOT assume it's relative to the current working directory. First explore the file system to locate the file before working on it.
* If asked to edit a file, edit the file directly using str_replace_editor, rather than creating a new file with a different filename.
* NEVER create multiple versions of the same file with different suffixes. Always modify the original file directly.
* When editing files, ensure the old_str parameter matches EXACTLY (including whitespace) to make replacements unique.
</FILE_OPERATIONS>

<CODE_QUALITY>
* Write clean, efficient code with minimal comments. Avoid redundancy in comments.
* When implementing solutions, focus on making the minimal changes needed to solve the problem.
* Before implementing any changes, first thoroughly understand the codebase through exploration using read-only commands.
* Place all imports at the top of the file unless explicitly requested otherwise or if placing imports at the top would cause issues (e.g., circular imports).
</CODE_QUALITY>

<WORKFLOW>
1. EXPLORATION: Use read-only bash commands (ls, find, grep, cat, git log, git diff) to explore relevant files and understand the context
2. ANALYSIS: Consider multiple approaches and select the most promising one based on the code structure
3. IMPLEMENTATION: Make focused, minimal changes using str_replace_editor to address the problem
4. VERIFICATION: Review your changes by reading the modified files to ensure they are correct
</WORKFLOW>

<SECURITY>
* Apply least privilege: scope file paths narrowly, avoid wildcards or broad recursive actions.
* NEVER exfiltrate secrets (tokens, keys, .env, PII, SSH keys, credentials, cookies).
* When encountering sensitive data: STOP, refuse, explain security risk.
</SECURITY>'''

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
                        'description': 'Absolute path to file or directory, e.g. `/workspace/file.py` or `/workspace`.',
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

    return [execute_bash, str_replace_editor, think, finish]


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
                        actions.append(fn_call)

        self.create()
        for fn_call in actions:
            try:
                self._execute_step({'response': fn_call_to_text(fn_call)})
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
        system_prompt = OPENHANDS_SYSTEM_PROMPT + "\n\n" + TOOL_PROMPT.format(description=convert_tools_to_description(tools_info))
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
        oracle_patch = instance_info.get('patch', '')
        
        canvas = "## SWE-bench Task\n\n"
        canvas += f"**Instance ID:** `{instance_id}`  \n"
        canvas += f"**Repository:** `{repo}`  \n"
        if difficulty:
            canvas += f"**Difficulty:** {difficulty}  \n"
        canvas += "\n---\n\n"
        
        if problem_statement:
            # Problem statement is GitHub issue markdown
            # Reduce header levels to make it less overwhelming (convert # to ###, ## to ####)
            problem_cleaned = problem_statement.strip()
            # Replace headers to reduce visual noise
            problem_cleaned = problem_cleaned.replace('\n# ', '\n### ')
            problem_cleaned = problem_cleaned.replace('\n## ', '\n#### ')
            problem_cleaned = problem_cleaned.replace('\n### ', '\n##### ')
            canvas += "### Problem Statement\n\n"
            canvas += problem_cleaned + "\n\n"
            canvas += "---\n\n"
        
        if hints_text:
            # Hints might contain markdown or plain text
            hints_cleaned = hints_text.strip()
            # Reduce header levels in hints too
            hints_cleaned = hints_cleaned.replace('\n# ', '\n### ')
            hints_cleaned = hints_cleaned.replace('\n## ', '\n#### ')
            hints_cleaned = hints_cleaned.replace('\n### ', '\n##### ')
            canvas += "### Hints\n\n"
            canvas += hints_cleaned + "\n\n"
            canvas += "---\n\n"
        
        if oracle_patch:
            # Patch is a diff format, display in diff code block
            canvas += "### Golden Patch\n\n"
            canvas += f"```\n{oracle_patch}\n```\n\n"
            canvas += "---\n\n"
        
        canvas += f"**Runtime ID:** `{self.runtime_id}`\n\n"
        return canvas


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
    conversation = condense_history(conversation)

    # Extract runtime_id and instance_id from meta_info if provided
    instance_id = None
    existing_runtime_id = None
    
    if meta_info:
        for line in meta_info.splitlines():
            if line.startswith('runtime_id:'):
                existing_runtime_id = line[len('runtime_id:'):].strip()
            if line.startswith('instance_id:'):
                instance_id = line[len('instance_id:'):].strip()

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
    
    # Create env_str from instance_info
    env_str = f"RepairEnv@{json.dumps(instance_info)}"

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

    # Special handling for \repo command
    if len(conversation) == 1 and conversation[0]['content'].startswith("\\repo"):
        yield "Hi there. How can I help you today?"
        return

    if conversation[-1]['content'] == '\\patch':
        # Generate and return the patch
        try:
            # Call step with \patch action - repo_env will handle it and return the patch
            # Pass the string directly, not as a dict, since step() expects a string
            patch_result = repo_env.step('\\patch', conversation=conversation)
            yield f"```diff\n{patch_result}\n```"
        except RuntimeServiceError as e:
            yield f"⚠️ Could not generate patch - runtime service unavailable: {e}"
        except Exception as e:
            yield f"⚠️ Error generating patch: {e}"
        return

    if conversation[-1]['content'] == '\\reward' or '###STOP###' in conversation[-1]['content']:
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

        finish_message = None
        if fn_call is not None and isinstance(fn_call, list) and len(fn_call) > 0:
            try:
                observation = repo_env.step(fn_call_to_text(fn_call), conversation=chat)
                yield {'info': f'runtime_id: {repo_env.runtime_id}'}
                for fn in fn_call:
                    if fn['name'] == 'finish':
                        finish_message = fn['arguments'].get('message', '')

            except RuntimeServiceError as e:
                yield f"\n\n⚠️ **Runtime Service Unavailable**\n\nCould not execute tool call. The environment service is temporarily unavailable. Please try again.\n\nError: {e}"
                return
            except Exception as e:
                observation = f"Error executing tool: {e}"

        if observation is None:
            observation = "No function call was detected. You must immediately call a tool (execute_bash, str_replace_editor, think, or finish) to continue working on the repository. Do not ask for confirmation - proceed directly with your next tool call. Use finish tool when the task is complete."
        chat.append({'role': 'user', 'content': observation})
        yield '<|tool|>' + observation + '<|/tool|>'
        
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
