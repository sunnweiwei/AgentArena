"""
Test script for swebench_env.py

This script tests the interactive SWE-bench environment interface:
- create_env()
- get_observations()
- env_step()
- get_reward()
- close_env()
"""
import sys
import time
import json
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 导入 swebench_env 模块
import runtime_service.swebench_env as swebench_env


def test_create_env():
    """Test creating an environment."""
    print("=" * 80)
    print("Testing create_env()...")
    print("=" * 80)
    
    try:
        # 创建环境
        env, meta_info = swebench_env.create_env(
            dataset_name="princeton-nlp/SWE-bench_Verified",
            instance_id="django__django-11333",
            split="test",
        )
        
        print(f"✓ Environment created successfully")
        print(f"  Environment type: {type(env)}")
        
        # 解析 meta_info
        meta = json.loads(meta_info)
        print(f"  Meta info: {json.dumps(meta, indent=2)}")
        
        # 检查环境属性
        print(f"  Interactive API URL: {env.interactive_api_url}")
        print(f"  LLM config path: {env.get_llm_config_path()}")
        
        return env
    except Exception as e:
        print(f"✗ Error creating environment: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_get_observations(env):
    """Test getting observations from the environment."""
    print("\n" + "=" * 80)
    print("Testing get_observations()...")
    print("=" * 80)
    
    try:
        # 等待一下，让交互式 API 服务有时间启动
        print("Waiting for interactive API service to be ready...")
        time.sleep(2)
        
        # 获取观察
        observation = swebench_env.get_observations(env)
        print(f"✓ Got observation:")
        print(f"{observation}")
        
        return observation
    except Exception as e:
        print(f"✗ Error getting observations: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_env_step(env):
    """Test submitting a response via env_step."""
    print("\n" + "=" * 80)
    print("Testing env_step()...")
    print("=" * 80)
    
    try:
        # 测试不同的响应格式
        test_cases = [
            {"response": "I will read the file first to understand the codebase.", "name": "terminal", "arguments": {"command": "ls -la"}},
            {"response": "I will read the file first to understand the codebase.", "name": "terminal", "arguments": {"command": "ls -all"}},
        #    {"name": "read_file", "arguments": {"path": "test.py"}},
        #    {"content": "Let me check the repository structure."},
        ]
        
        for i, fn_call in enumerate(test_cases, 1):
            print(f"\nTest case {i}: {fn_call}")
            result = swebench_env.env_step(env, fn_call)
            print(f"✓ Response submitted:")
            print(result)
            print(type(result))
            time.sleep(1)
        
        return True
    except Exception as e:
        print(f"✗ Error in env_step: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_get_reward(env):
    """Test getting reward from the environment."""
    print("\n" + "=" * 80)
    print("Testing get_reward()...")
    print("=" * 80)
    
    try:
        reward = swebench_env.get_reward(env)
        print(f"✓ Got reward: {reward}")
        return reward
    except Exception as e:
        print(f"✗ Error getting reward: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_close_env(env):
    """Test closing the environment."""
    print("\n" + "=" * 80)
    print("Testing close_env()...")
    print("=" * 80)
    
    try:
        swebench_env.close_env(env)
        print(f"✓ Environment closed successfully")
        return True
    except Exception as e:
        print(f"✗ Error closing environment: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("SWE-bench Environment Test Suite")
    print("=" * 80)
    
    env = None
    try:
        # Test 1: Create environment
        env = test_create_env()
        if env is None:
            print("\n✗ Failed to create environment. Aborting tests.")
            return
        
        # Test 2: Get observations
        observation = test_get_observations(env)
        
        # Test 3: Submit response
        test_env_step(env)
        
        # Test 4: Get reward
        reward = test_get_reward(env)
        
        # Test 5: Close environment
        test_close_env(env)
        
        print("\n" + "=" * 80)
        print("All tests completed!")
        print("=" * 80)
        print("\nNote: The interactive API service and background task are still running.")
        print("The environment will be cleaned up when the script exits.")
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
    except Exception as e:
        print(f"\n\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        if env is not None:
            try:
                print("\nCleaning up environment...")
                swebench_env.close_env(env)
            except Exception as e:
                print(f"Error during cleanup: {e}")


if __name__ == "__main__":
    main()

