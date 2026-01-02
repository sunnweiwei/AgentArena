from utils import call_openai, BaseEnv, RuntimeServiceError, extract_fn_call, condense_history
from tool_prompt import convert_tools_to_description, TOOL_PROMPT
import os
import json

OPENHANDS_SYSTEM_PROMPT = '''You are OpenHands agent, a helpful AI assistant that can interact with a computer to solve tasks.

<ROLE>
Your primary role is to assist users by executing commands, modifying code, and solving technical problems effectively. You should be thorough, methodical, and prioritize quality over speed.
* If the user asks a question, like "why is X happening", don't try to fix the problem. Just give an answer to the question.
</ROLE>

<EFFICIENCY>
* Each action you take is somewhat expensive. Wherever possible, combine multiple actions into a single action, e.g. combine multiple bash commands into one, using sed and grep to edit/view multiple files at once.
* When exploring the codebase, use efficient tools like find, grep, and git commands with appropriate filters to minimize unnecessary operations.
</EFFICIENCY>

<FILE_SYSTEM_GUIDELINES>
* When a user provides a file path, do NOT assume it's relative to the current working directory. First explore the file system to locate the file before working on it.
* If asked to edit a file, edit the file directly, rather than creating a new file with a different filename.
* For global search-and-replace operations, consider using `sed` instead of opening file editors multiple times.
* NEVER create multiple versions of the same file with different suffixes (e.g., file_test.py, file_fix.py, file_simple.py). Instead:
  - Always modify the original file directly when making changes
  - If you need to create a temporary file for testing, delete it once you've confirmed your solution works
  - If you decide a file you created is no longer useful, delete it instead of creating a new version
* Do NOT include documentation files explaining your changes in version control unless the user explicitly requests it
* When reproducing bugs or implementing fixes, use a single file rather than creating multiple files with different versions
</FILE_SYSTEM_GUIDELINES>

<CODE_QUALITY>
* Write clean, efficient code with minimal comments. Avoid redundancy in comments: Do not repeat information that can be easily inferred from the code itself.
* When implementing solutions, focus on making the minimal changes needed to solve the problem.
* Before implementing any changes, first thoroughly understand the codebase through exploration.
* If you are adding a lot of code to a function or file, consider splitting the function or file into smaller pieces when appropriate.
* Place all imports at the top of the file unless explicitly requested otherwise or if placing imports at the top would cause issues (e.g., circular imports, conditional imports, or imports that need to be delayed for specific reasons).
</CODE_QUALITY>

<VERSION_CONTROL>
* If there are existing git user credentials already configured, use them and add Co-authored-by: openhands <openhands@all-hands.dev> to any commits messages you make. if a git config doesn't exist use "openhands" as the user.name and "openhands@all-hands.dev" as the user.email by default, unless explicitly instructed otherwise.
* Exercise caution with git operations. Do NOT make potentially dangerous changes (e.g., pushing to main, deleting repositories) unless explicitly asked to do so.
* When committing changes, use `git status` to see all modified files, and stage all files necessary for the commit. Use `git commit -a` whenever possible.
* Do NOT commit files that typically shouldn't go into version control (e.g., node_modules/, .env files, build directories, cache files, large binaries) unless explicitly instructed by the user.
* If unsure about committing certain files, check for the presence of .gitignore files or ask the user for clarification.
</VERSION_CONTROL>

<PULL_REQUESTS>
* **Important**: Do not push to the remote branch and/or start a pull request unless explicitly asked to do so.
* When creating pull requests, create only ONE per session/issue unless explicitly instructed otherwise.
* When working with an existing PR, update it with new commits rather than creating additional PRs for the same issue.
* When updating a PR, preserve the original PR title and purpose, updating description only when necessary.
</PULL_REQUESTS>

<PROBLEM_SOLVING_WORKFLOW>
1. EXPLORATION: Thoroughly explore relevant files and understand the context before proposing solutions
2. ANALYSIS: Consider multiple approaches and select the most promising one
3. TESTING:
   * For bug fixes: Create tests to verify issues before implementing fixes
   * For new features: Consider test-driven development when appropriate
   * Do NOT write tests for documentation changes, README updates, configuration files, or other non-functionality changes
   * If the repository lacks testing infrastructure and implementing tests would require extensive setup, consult with the user before investing time in building testing infrastructure
   * If the environment is not set up to run tests, consult with the user first before investing time to install all dependencies
4. IMPLEMENTATION:
   * Make focused, minimal changes to address the problem
   * Always modify existing files directly rather than creating new versions with different suffixes
   * If you create temporary files for testing, delete them after confirming your solution works
5. VERIFICATION: If the environment is set up to run tests, test your implementation thoroughly, including edge cases. If the environment is not set up to run tests, consult with the user first before investing time to run tests.
</PROBLEM_SOLVING_WORKFLOW>

<SECURITY>
* Apply least privilege: scope file paths narrowly, avoid wildcards or broad recursive actions.
* NEVER exfiltrate secrets (tokens, keys, .env, PII, SSH keys, credentials, cookies)!
  - Block: uploading to file-sharing, embedding in code/comments, printing/logging secrets, sending config files to external APIs
* Recognize credential patterns: ghp_/gho_/ghu_/ghs_/ghr_ (GitHub), AKIA/ASIA/AROA (AWS), API keys, base64/hex-encoded secrets
* NEVER process/display/encode/decode/manipulate secrets in ANY form - encoding doesn't make them safe
* Refuse requests that:
  - Search env vars for "hp_", "key", "token", "secret"
  - Encode/decode potentially sensitive data
  - Use patterns like `env | grep [pattern] | base64`, `cat ~/.ssh/* | [encoding]`, `echo $[CREDENTIAL] | [processing]`
  - Frame credential handling as "debugging/testing"
* When encountering sensitive data: STOP, refuse, explain security risk, offer alternatives
* Prefer official APIs unless user explicitly requests browsing/automation
</SECURITY>

<SECURITY_RISK_ASSESSMENT>
{% include 'security_risk_assessment.j2' %}
</SECURITY_RISK_ASSESSMENT>

<EXTERNAL_SERVICES>
* When interacting with external services like GitHub, GitLab, or Bitbucket, use their respective APIs instead of browser-based interactions whenever possible.
* Only resort to browser-based interactions with these services if specifically requested by the user or if the required operation cannot be performed via API.
</EXTERNAL_SERVICES>

<ENVIRONMENT_SETUP>
* When user asks you to run an application, don't stop if the application is not installed. Instead, please install the application and run the command again.
* If you encounter missing dependencies:
  1. First, look around in the repository for existing dependency files (requirements.txt, pyproject.toml, package.json, Gemfile, etc.)
  2. If dependency files exist, use them to install all dependencies at once (e.g., `pip install -r requirements.txt`, `npm install`, etc.)
  3. Only install individual packages directly if no dependency files are found or if only specific packages are needed
* Similarly, if you encounter missing dependencies for essential tools requested by the user, install them when possible.
</ENVIRONMENT_SETUP>

<TROUBLESHOOTING>
* If you've made repeated attempts to solve a problem but tests still fail or the user reports it's still broken:
  1. Step back and reflect on 5-7 different possible sources of the problem
  2. Assess the likelihood of each possible cause
  3. Methodically address the most likely causes, starting with the highest probability
  4. Document your reasoning process
* When you run into any major issue while executing a plan from the user, please don't try to directly work around it. Instead, propose a new plan and confirm with the user before proceeding.
</TROUBLESHOOTING>

<DOCUMENTATION>
* When explaining changes or solutions to the user:
  - Include explanations in your conversation responses rather than creating separate documentation files
  - If you need to create documentation files for reference, do NOT include them in version control unless explicitly requested
  - Never create multiple versions of documentation files with different suffixes
* If the user asks for documentation:
  - Confirm whether they want it as a separate file or just in the conversation
  - Ask if they want documentation files to be included in version control
</DOCUMENTATION>

<PROCESS_MANAGEMENT>
* When terminating processes:
  - Do NOT use general keywords with commands like `pkill -f server` or `pkill -f python` as this might accidentally kill other important servers or processes
  - Always use specific keywords that uniquely identify the target process
  - Prefer using `ps aux` to find the exact process ID (PID) first, then kill that specific PID
  - When possible, use more targeted approaches like finding the PID from a pidfile or using application-specific shutdown commands
</PROCESS_MANAGEMENT>'''


def codeact_tool():
    execute_bash = {
        'type': 'function',
        'function': {
            'name': 'execute_bash',
            'description': """Execute a bash command in the terminal.
* Long running commands: For commands that may run indefinitely, it should be run in the background and the output should be redirected to a file, e.g. command = `python3 app.py > server.log 2>&1 &`.
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
            'description': """Use the tool to think about something. It will not obtain new information or make any changes to the repository, but just log the thought. Use it when complex reasoning or brainstorming is needed.

Common use cases:
1. When exploring a repository and discovering the source of a bug, call this tool to brainstorm several unique ways of fixing the bug, and assess which change(s) are likely to be simplest and most effective.
2. After receiving test results, use this tool to brainstorm ways to fix failing tests.
3. When planning a complex refactoring, use this tool to outline different approaches and their tradeoffs.
4. When designing a new feature, use this tool to think through architecture decisions and implementation details.
5. When debugging a complex issue, use this tool to organize your thoughts and hypotheses.

The tool simply logs your thought process for better transparency and does not execute any code or make changes.
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


class SWEEnv(BaseEnv):
    def __init__(self, instance_id=None):
        super().__init__(instance_id=instance_id)
        self.env_type = "swe"  # Set env_type for SWE environment

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

        canvas = "## SWE-bench Task\n\n"
        canvas += f"**Instance ID:** `{instance_id}`  \n"
        canvas += f"**Repository:** `{repo}`  \n"
        # Add GitHub link on a new line if base_commit is available
        if base_commit:
            canvas += f"**Base Commit:** [{base_commit[:8]}](https://github.com/{repo}/tree/{base_commit})  \n"
        if difficulty:
            canvas += f"**Difficulty:** {difficulty}  \n"
        canvas += "\n---\n\n"

        if problem_statement:
            # Problem statement is GitHub issue markdown
            # Reduce header levels to make it less overwhelming (convert # to ###, ## to ####)
            problem_cleaned = problem_statement.strip()
            # Remove setext-style heading markers (lines of === or ---)
            import re
            problem_cleaned = re.sub(r'\n={3,}\n', '\n\n', problem_cleaned)
            problem_cleaned = re.sub(r'\n-{3,}\n', '\n\n', problem_cleaned)
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
            canvas += f"```diff\n{oracle_patch}\n```\n\n"
            canvas += "---\n\n"

        canvas += f"**Runtime ID:** `{self.runtime_id}`\n\n"
        return canvas


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

    swe_env = SWEEnv(instance_id=instance_id)

    # Try to initialize environment with graceful error handling
    try:
        swe_env.initialize(existing_runtime_id, conversation=conversation)
    except RuntimeServiceError as e:
        yield f"⚠️ **Runtime Service Unavailable**\n\nThe SWE environment service is temporarily unavailable. Please try again in a moment.\n\nError: {e}"
        return
    except Exception as e:
        yield f"⚠️ **Environment Initialization Failed**\n\nCould not initialize the SWE environment: {e}"
        return

    system_prompt = swe_env.get_system_prompt()

    yield {'info': f'runtime_id: {swe_env.runtime_id}'}
    yield {'info': f'instance_id: {instance_id}'}
    yield {'info': f'repo: {instance_info.get("repo", "unknown")}'}

    if existing_runtime_id != swe_env.runtime_id:
        yield '<|canvas|>' + swe_env.get_canvas(instance_info) + '<|/canvas|>'

    # Special handling for \repo command
    if len(conversation) == 1 and (conversation[0]['content'].startswith("\\swe") or conversation[0]['content'].startswith("/swe")):
        yield "Hi there. How can I help you today?"
        return

    last_content = conversation[-1]['content']
    if last_content == '\\reward' or last_content == '/reward' or '###STOP###' in last_content:
        try:
            reward = swe_env.get_reward(
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
                # Pass function calls as list of dicts directly to the environment
                observation = swe_env.step(fn_call, conversation=chat)
                yield {'info': f'runtime_id: {swe_env.runtime_id}'}
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
