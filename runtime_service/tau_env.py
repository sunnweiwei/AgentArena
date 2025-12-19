from tau_bench.envs import get_env
from tau_bench.types import Action
import json

# Meta information about this environment module
meta_info = "Tau-bench environment for airline and retail customer service tasks"


def create_env(env_name='airline', task_index=None):
    env = get_env(
        env_name,
        user_strategy='llm',
        user_model='gpt-4o',
        task_split='test',
        user_provider='openai',
        task_index=task_index,
    )

    # If task_index is None, don't pass it to reset() - let tau-bench pick randomly
    if task_index is not None:
        initial = env.reset(task_index=task_index)
    else:
        initial = env.reset()
    
    initial_question = initial.observation
    tools_info = env.tools_info
    wiki = env.wiki
    instruction = env.task.instruction
    actual_task_index = env.task_index
    return env, json.dumps({'initial_question': initial_question,
                            'tools_info': tools_info,
                            'wiki': wiki,
                            'instruction': instruction,
                            'task_index': actual_task_index,
                            'env_name': env_name
                            })


def convert_value_to_type(value, expected_type):
    """
    Convert a value to the expected type based on type hints.
    Handles strings that should be parsed to other types.
    """
    # If value is already the correct type, return as is
    if expected_type == 'any' or expected_type is None:
        return value

    # If it's a string, try to parse it
    if isinstance(value, str):
        # Try to parse JSON strings (arrays, objects)
        if value.startswith('[') or value.startswith('{'):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, ValueError):
                pass

        # Convert to int
        if expected_type in ['int', 'integer']:
            try:
                return int(value)
            except (ValueError, TypeError):
                pass

        # Convert to float
        if expected_type in ['float', 'number']:
            try:
                return float(value)
            except (ValueError, TypeError):
                pass

        # Convert to bool
        if expected_type in ['bool', 'boolean']:
            if value.lower() in ['true', 'yes', '1']:
                return True
            if value.lower() in ['false', 'no', '0']:
                return False

    return value


def convert_arguments_by_schema(function_name, arguments, tools_info):
    """
    Convert all arguments to match their expected types from the function schema.
    """
    converted_args = arguments.copy()

    # Find the tool schema
    tool_schema = None
    for tool in tools_info:
        if tool.get('name') == function_name or tool.get('function', {}).get('name') == function_name:
            tool_schema = tool.get('function', tool)
            break

    if not tool_schema or 'parameters' not in tool_schema:
        # No schema found, just try to parse JSON strings
        for key, value in converted_args.items():
            if isinstance(value, str) and (value.startswith('[') or value.startswith('{')):
                try:
                    converted_args[key] = json.loads(value)
                except:
                    pass
        return converted_args

    # Get parameter definitions
    parameters = tool_schema['parameters']
    properties = parameters.get('properties', {})

    # Convert each argument according to its schema
    for param_name, param_value in converted_args.items():
        if param_name in properties:
            param_schema = properties[param_name]
            expected_type = param_schema.get('type', 'any')

            # Convert top-level parameter
            converted_args[param_name] = convert_value_to_type(param_value, expected_type)

            # Handle arrays with object items
            if expected_type == 'array' and isinstance(converted_args[param_name], list):
                items_schema = param_schema.get('items', {})
                if items_schema.get('type') == 'object' and 'properties' in items_schema:
                    # Convert each object in the array
                    for i, item in enumerate(converted_args[param_name]):
                        if isinstance(item, dict):
                            for field_name, field_schema in items_schema['properties'].items():
                                if field_name in item:
                                    field_type = field_schema.get('type', 'any')
                                    item[field_name] = convert_value_to_type(item[field_name], field_type)

    return converted_args


def env_step(env, fn_call: dict):
    """
    Execute a step in the environment with automatic type conversion based on function schema.
    """
    function_name = fn_call['name']
    arguments = fn_call['arguments']

    # Get tools info from environment
    tools_info = env.tools_info if hasattr(env, 'tools_info') else []

    # Convert arguments to match schema types
    converted_arguments = convert_arguments_by_schema(function_name, arguments, tools_info)

    # Create action and execute
    action = Action(name=function_name, kwargs=converted_arguments)
    observation = env.step(action)
    return observation.observation


def get_reward(env, **kwargs):
    reward = env.calculate_reward()
    return reward.reward
