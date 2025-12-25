import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from runtime_service.swebench_env_impl.core import SweBenchInteractiveEnv
from runtime_service.swebench_env_impl.load_single_task import test_single_task

# 启动交互式环境（会自动启动 API 服务）
env = SweBenchInteractiveEnv(
    dataset_name="princeton-nlp/SWE-bench_Verified",
    instance_id="django__django-11333",
    interactive_api_port=8057,
)

# 获取 LLM config 路径（指向交互式服务）
llm_config_path = env.get_llm_config_path()

print(llm_config_path)

import time

time.sleep(1000000)


# 直接传给 test_single_task，就像传普通的 LLM config 一样
test_single_task(
    instance_id="django__django-11333",
    llm_config_path=llm_config_path,  # 这就是交互式服务的 config
    # ... 其他参数
)

# 完成后清理
env.close()