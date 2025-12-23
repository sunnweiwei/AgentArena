from utils import call_openai, BaseEnv, RuntimeServiceError, extract_fn_call, split_agent_markup, keep_first_n_words
from tool_prompt import convert_tools_to_description, TOOL_PROMPT
import pandas as pd


SEARCH_SYSTEM_PROMPT_v3 = '''You are a deep research agent. You need to answer the given question by interacting with a search engine, using the search and open tools provided. Please perform reasoning and use the tools step by step, in an interleaved manner. You may use the search and open tools multiple times.

Follow this structured protocol for to find the answer

### Phase 1: Deconstruction & Strategy

1.  **Deconstruct the Query:**
    * Analyze the user's prompt to identify the core question(s).
    * Isolate key entities, concepts, and the relationships between them.
    * Explicitly list all constraints, conditions, and required data points (e.g., dates, quantities, specific names).
2.  **Hypothesize & Brainstorm:**
    * Based on your knowledge, brainstorm potential search vectors, keywords, synonyms, and related topics that could yield relevant information.
    * Consider multiple angles of inquiry to approach the problem.
3.  **Verification Checklist:**
    * Create a **Verification Checklist** based on the query's constraints and required data points. This checklist will be your guide throughout the process and used for final verification.

### Phase 2: Iterative Research & Discovery

**Tool Usage:**
* **Tools:**
    * `search`: Use for broad discovery of sources and to get initial snippets.
    * `open_page`: **Mandatory follow-up** for any promising `search` result. Snippets are insufficient; you must analyze the full context of the source document.
* **Query Strategy:**
    * Start with moderately broad queries to map the information landscape. Narrow your focus as you learn more.
    * Do not repeat the exact same query. If a query fails, rephrase it or change your angle of attack.
    * Execute a **minimum of 5 tool calls** for simple queries and up to **50 tool calls** for complex ones. Do not terminate prematurely.
* **Post-Action Analysis:** After every tool call, briefly summarize the key findings from the result, extract relevant facts, and explicitly state how this new information affects your next step in the OODA loop.
* **<IMPORTANT>Never simulate tool call output<IMPORTANT>**

You will execute your research plan using an iterative OODA loop (Observe, Orient, Decide, Act).

1.  **Observe:** Review all gathered information. Identify what is known and, more importantly, what knowledge gaps remain according to your research plan.
2.  **Orient:** Analyze the situation. Is the current line of inquiry effective? Are there new, more promising avenues? Refine your understanding of the topic based on the search results so far.
3.  **Decide:** Choose the single most effective next action. This could be a broader query to establish context, a highly specific query to find a key data point, or opening a promising URL.
4.  **Act:** Execute the chosen action using the available tools. After the action, return to **Observe**.

### Phase 3: Synthesis & Analysis

* **Continuous Synthesis:** Throughout the research process, continuously integrate new information with existing knowledge. Build a coherent narrative and understanding of the topic.
* **Triangulate Critical Data:** For any crucial fact, number, date, or claim, you must seek to verify it across at least two independent, reliable sources. Note any discrepancies.
* **Handle Dead Ends:** If you are blocked, do not give up. Broaden your search scope, try alternative keywords, or research related contextual information to uncover new leads. Assume a discoverable answer exists and exhaust all reasonable avenues.
* **Maintain a "Fact Sheet":** Internally, keep a running list of key facts, figures, dates, and their supporting sources. This will be crucial for the final report.

### Phase 4: Verification & Final Report Formulation

1.  **Systematic Verification:** Before writing the final answer, halt your research and review your **Verification Checklist** created in Phase 1. For each item on the checklist, confirm you have sufficient, well-supported evidence from the documents you have opened.
2.  **Mandatory Re-research:** If any checklist item is unconfirmed or the evidence is weak, it is **mandatory** to return to Phase 2 to conduct further targeted research. Do not formulate an answer based on incomplete information.
3.  **Never give up**, no matter how complex the query, you will not give up until you find the corresponding information.
4.  **Construct the Final Report:**
    * Once all checklist items are confidently verified, synthesize all gathered facts into a comprehensive and well-structured answer.
    * Directly answer the user's original query.
    * Ensure all claims, numbers, and key pieces of information in your report are clearly supported by the research you conducted.

Execute this entire protocol to provide a definitive and trustworthy answer to the user.

* You can search one queries:
<function=search>
<parameter=query>Query</parameter>
<parameter=topk>10</parameter>
</function>

* Or you can search multiple queries in one turn by including multiple <function=search> actions, e.g.
<function=search>
<parameter=query>Query1</parameter>
<parameter=topk>5</parameter>
</function>
<function=search>
<parameter=query>Query2</parameter>
<parameter=topk>5</parameter>
</function>

* Use open_page to fetch a web page:
<function=open_page>
<parameter=docid>docid</parameter>
</function>
or
<function=open_page>
<parameter=url>url</parameter>
</function>

Your response should contain:
Explanation: {{your explanation for your final answer. For this explanation section only, you should cite your evidence documents inline by enclosing their docids in square brackets [] at the end of sentences. For example, [20].}}
Exact Answer: {{your succinct, final answer}}
Confidence: {{your confidence score between 0% and 100% for your answer}}
Use finish tool to submit your answer.

<IMPORTANT>
- Always call a tool to get search results; never simulate a tool call.
- You may provide optional reasoning for your function call in natural language BEFORE the function call, but NOT after.
- **CRITICAL: You operate autonomously. NEVER ask the user for confirmation or permission to proceed. Always execute tool calls immediately when you decide on the next action. Do not say things like "Please confirm" or "Should I proceed" - just proceed directly with your tool calls.**
- When you receive a message saying to continue, immediately proceed with your next tool call without any confirmation request.
</IMPORTANT>
'''

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
        self.env_type = "bc"  # Set env_type for bc environment

    def restore(self, conversation):
        """Restore environment **without** replaying actions."""
        self.create()  # Uses self.env_type = "bc"

    def get_system_prompt(self):
        tools_info = bc_search_tool()
        system_prompt = SEARCH_SYSTEM_PROMPT_v3 + "\n\n" + TOOL_PROMPT.format(description=convert_tools_to_description(tools_info))
        return system_prompt

    def get_canvas(self, data_source):
        return (f"**Full Question:**\n\n{self.meta_info['question']}\n\n"
                f"**Label Answer:**\n\n{self.meta_info['label_answer']}\n\n"
                f"**Data Source**: {data_source}\n\n"
                f"**Runtime:** {self.runtime_id}\n\n")


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

    # Clean conversation - remove canvas, think, etc. before sending to model
    conversation = condense_history(conversation)

    # Extract runtime_id and env_name from meta_info if provided
    question = None
    label_answer = None
    existing_runtime_id = None
    data_source = None
    predicted_answer = None
    explanation = None
    confidence = None
    if meta_info:
        for line in meta_info.splitlines():
            if line.startswith('runtime_id:'):
                existing_runtime_id = line[len('runtime_id:'):].strip()
            if line.startswith('question:'):
                question = line[len('question:'):].strip()
            if line.startswith('label_answer:'):
                label_answer = line[len('label_answer:'):].strip()
            if line.startswith('data_source:'):
                data_source = line[len('data_source:'):].strip()
            if line.startswith('predicted_answer:'):
                predicted_answer = line[len('predicted_answer:'):].strip()

    if question is None or label_answer is None:
        import os
        data_path = os.path.join(os.path.dirname(__file__), "data", "bc_test.parquet")
        df = pd.read_parquet(data_path)
        row = df.sample(1).iloc[0]
        question = row['extra_info']['query']
        label_answer = row['extra_info']['answer']
        data_source = row['data_source']

    bc_env = BCEnv(question=question, label_answer=label_answer)

    # Try to initialize environment with graceful error handling
    try:
        bc_env.initialize(existing_runtime_id, conversation=conversation)
    except RuntimeServiceError as e:
        yield f"⚠️ **Runtime Service Unavailable**\n\nThe tau-bench environment service is temporarily unavailable. Please try again in a moment.\n\nError: {e}"
        return
    except Exception as e:
        yield f"⚠️ **Environment Initialization Failed**\n\nCould not initialize the environment: {e}"
        return

    system_prompt = bc_env.get_system_prompt()

    yield {'info': f'runtime_id: {bc_env.runtime_id}'}
    yield {'info': f'question: {bc_env.meta_info["question"]}'}
    yield {'info': f'label_answer: {bc_env.meta_info["label_answer"]}'}
    yield {'info': f'data_source: {data_source}'}

    if existing_runtime_id != bc_env.runtime_id:
        yield '<|canvas|>' + bc_env.get_canvas(data_source) + '<|/canvas|>'

    # Special handling for \tau command
    if len(conversation) == 1 and conversation[0]['content'].startswith("\\bc"):
        yield "Hi there. How can I help you today?"
        return

    if conversation[-1]['content'] == '\\reward' or '###STOP###' in conversation[-1]['content']:
        try:
            reward = bc_env.get_reward(label_answer=label_answer, predicted_answer=predicted_answer, explanation=explanation, confidence=confidence)
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
                    if fn['name'] == 'finish':
                        predicted_answer = fn['arguments'].get('answer', "")
                        yield {'info': f'predicted_answer: {predicted_answer}'}
                        explanation = fn['arguments'].get('explanation', None)
                        confidence = fn['arguments'].get('confidence', None)
                    observation = bc_env.step(fn, conversation=chat)
                yield {'info': f'runtime_id: {bc_env.runtime_id}'}
            except RuntimeServiceError as e:
                yield f"\n\n⚠️ **Runtime Service Unavailable**\n\nCould not execute tool call. The environment service is temporarily unavailable. Please try again.\n\nError: {e}"
                return
            except Exception as e:
                observation = f"Error executing tool: {e}"

        if observation is None:
            observation = "No function call was detected. You must immediately call a tool (search or open_page) to continue your research. Do not ask for confirmation - proceed directly with your next tool call. Use finish tool to submit answer."
            # break
        chat.append({'role': 'user', 'content': observation})
        yield '<|tool|>' + observation + '<|/tool|>'
        if observation == 'finish':
            yield f"## Answer\n\n{predicted_answer}\n\nConfidence: {confidence}\n\n{explanation}"
            break
    return

# for chunk in agent_loop("I'm looking to book a one-way flight from New York to Seattle on May 20."):
#     print(chunk)
#     print('\n\n')


# runtime_id, meta_info = create_env()
# print(runtime_id)
# obs = env_step(runtime_id, {'name': 'search_direct_flight', 'arguments': {'origin': 'JFK', 'destination': 'SEA', 'date': '2024-05-20'}})
# print(obs)
