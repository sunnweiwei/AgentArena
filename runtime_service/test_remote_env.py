import runtime_service.swebench_env_remote as swebench_env_remote

env, meta = swebench_env_remote.create_env(
    dataset_name="princeton-nlp/SWE-bench_Verified",
    instance_id="django__django-11333",
    interactive_api_port=8053,  # 可选
    server_url="http://localhost:8132"  # 可选
)

print(f"Created env with session_id: {env.session_id}")
print(f"Server URL: {env.server_url}")
print(f"Meta: {meta}")

print("Getting observations...")
env.get_observations() # get the initial observation
print(env.step({"response": "I will read the file first to understand the codebase.", "name": "terminal_wrong", "arguments": {"command": "ls -all"}}))
print(env.step({"response": "I will read the file first to understand the codebase."}))
print(env.close()) # get the reward