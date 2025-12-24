import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from runtime_service.swebench_env_impl.core import SweBenchInteractiveEnv
from benchmarks.swebench.test_single_task import test_single_task


# 直接传给 test_single_task，就像传普通的 LLM config 一样
test_single_task(
    instance_id="django__django-11333",
    llm_config_path="benchmarks/.llm_config/openai.json",  # 这就是交互式服务的 config
    # ... 其他参数
)