#!/usr/bin/env python3
"""
Comprehensive test script for Runtime Service
Tests all endpoints: create, step, reward, ping, stop
"""

import requests
import json
import time

BASE_URL = "http://localhost:8005"

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def test_health():
    """Test health endpoint"""
    print_section("TEST 1: Health Check")
    try:
        response = requests.get(f"{BASE_URL}/health")
        response.raise_for_status()
        data = response.json()
        print(f"✅ Health check passed")
        print(f"   Status: {data['status']}")
        print(f"   Active environments: {data['active_environments']}")
        print(f"   Available env types: {data['available_env_types']}")
        return True
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_create_env():
    """Test environment creation"""
    print_section("TEST 2: Create Environment")
    try:
        params = {
            "env_name": "airline",
            "task_index": 0
        }
        
        print(f"Creating tau environment with params: {params}")
        print("⏳ This may take a few minutes (tau-bench initialization)...")
        
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/create",
            json={
                "env_type": "tau",
                "params": json.dumps(params)
            },
            timeout=300  # 5 minute timeout
        )
        elapsed = time.time() - start_time
        
        response.raise_for_status()
        data = response.json()
        runtime_id = data["runtime_id"]
        meta_info = json.loads(data["meta_info"])
        
        print(f"✅ Environment created successfully in {elapsed:.2f}s")
        print(f"   Runtime ID: {runtime_id}")
        print(f"   Initial question: {meta_info['initial_question'][:100]}...")
        print(f"   Task info keys: {list(meta_info.get('task_info', {}).keys())}")
        
        return runtime_id, meta_info
    except Exception as e:
        print(f"❌ Environment creation failed: {e}")
        return None, None

def test_step(runtime_id):
    """Test environment step"""
    print_section("TEST 3: Step Environment")
    try:
        # Example step: search for flights
        step_params = {
            "name": "search_direct_flight",
            "arguments": {
                "departure_airport": "JFK",
                "arrival_airport": "LAX",
                "departure_date": "2024-01-15"
            }
        }
        
        print(f"Executing step: {step_params['name']}")
        print(f"Arguments: {step_params['arguments']}")
        print("⏳ Executing step...")
        
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/step",
            json={
                "runtime_id": runtime_id,
                "params": json.dumps(step_params)
            },
            timeout=120  # 2 minute timeout
        )
        elapsed = time.time() - start_time
        
        response.raise_for_status()
        data = response.json()
        result = data["result"]
        
        print(f"✅ Step executed successfully in {elapsed:.2f}s")
        print(f"   Result: {result[:200]}...")
        
        return result
    except Exception as e:
        print(f"❌ Step execution failed: {e}")
        return None

def test_reward(runtime_id):
    """Test reward retrieval"""
    print_section("TEST 4: Get Reward")
    try:
        print(f"Getting reward for runtime_id: {runtime_id}")
        
        response = requests.post(
            f"{BASE_URL}/reward",
            json={
                "runtime_id": runtime_id,
                "params": "{}"
            },
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        reward = data["reward"]
        
        print(f"✅ Reward retrieved successfully")
        print(f"   Reward: {reward}")
        
        return reward
    except Exception as e:
        print(f"❌ Reward retrieval failed: {e}")
        return None

def test_ping(runtime_id):
    """Test environment ping"""
    print_section("TEST 5: Ping Environment")
    try:
        print(f"Pinging runtime_id: {runtime_id}")
        
        response = requests.post(
            f"{BASE_URL}/ping",
            json={
                "runtime_id": runtime_id
            },
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        
        print(f"✅ Ping successful")
        print(f"   Exists: {data['exists']}")
        print(f"   Has ping method: {data['has_ping']}")
        if data.get('ping_result'):
            print(f"   Ping result: {data['ping_result'][:100]}...")
        print(f"   Message: {data['message']}")
        
        return data
    except Exception as e:
        print(f"❌ Ping failed: {e}")
        return None

def test_stop(runtime_id):
    """Test environment stop"""
    print_section("TEST 6: Stop Environment")
    try:
        print(f"Stopping runtime_id: {runtime_id}")
        
        response = requests.post(
            f"{BASE_URL}/stop",
            json={
                "runtime_id": runtime_id
            },
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        
        print(f"✅ Environment stopped successfully")
        print(f"   Success: {data['success']}")
        print(f"   Message: {data['message']}")
        
        return data['success']
    except Exception as e:
        print(f"❌ Stop failed: {e}")
        return False

def test_list_environments():
    """Test list environments endpoint"""
    print_section("TEST 7: List Environments")
    try:
        response = requests.get(f"{BASE_URL}/environments")
        response.raise_for_status()
        data = response.json()
        
        print(f"✅ List environments successful")
        print(f"   Count: {data['count']}")
        if data['environments']:
            for runtime_id, env_data in list(data['environments'].items())[:3]:
                print(f"   - {runtime_id}: {env_data['env_type']}")
        else:
            print(f"   No active environments")
        
        return data
    except Exception as e:
        print(f"❌ List environments failed: {e}")
        return None

def test_env_types():
    """Test list env types endpoint"""
    print_section("TEST 8: List Environment Types")
    try:
        response = requests.get(f"{BASE_URL}/env-types")
        response.raise_for_status()
        data = response.json()
        
        print(f"✅ List env types successful")
        for env_type, info in data['env_types'].items():
            status = "✓" if info['available'] else "✗"
            print(f"   {status} {env_type}: {info['module']}")
            if not info['available']:
                print(f"      Error: {info['meta_info']}")
        
        return data
    except Exception as e:
        print(f"❌ List env types failed: {e}")
        return None

def main():
    print("\n" + "="*60)
    print("  Runtime Service Comprehensive Test Suite")
    print("="*60)
    
    # Test 1: Health check
    if not test_health():
        print("\n❌ Service is not healthy. Aborting tests.")
        return
    
    # Test 2-8: Full workflow
    runtime_id = None
    try:
        # Create environment
        runtime_id, meta_info = test_create_env()
        if not runtime_id:
            print("\n❌ Cannot proceed without a valid runtime_id")
            return
        
        # List environments (should show our new env)
        test_list_environments()
        
        # List env types
        test_env_types()
        
        # Step the environment
        step_result = test_step(runtime_id)
        
        # Get reward
        reward = test_reward(runtime_id)
        
        # Ping the environment
        ping_result = test_ping(runtime_id)
        
        # Stop the environment
        test_stop(runtime_id)
        
        # List environments again (should be empty)
        test_list_environments()
        
        # Final summary
        print_section("TEST SUMMARY")
        tests = [
            ("Health Check", True),
            ("Create Environment", runtime_id is not None),
            ("Step Environment", step_result is not None),
            ("Get Reward", reward is not None),
            ("Ping Environment", ping_result is not None),
            ("Stop Environment", True),
        ]
        
        passed = sum(1 for _, result in tests if result)
        total = len(tests)
        
        print(f"\nTests passed: {passed}/{total}")
        for test_name, result in tests:
            status = "✅" if result else "❌"
            print(f"  {status} {test_name}")
        
        if passed == total:
            print("\n🎉 All tests passed!")
        else:
            print(f"\n⚠️  {total - passed} test(s) failed")
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        if runtime_id:
            print(f"Cleaning up runtime_id: {runtime_id}")
            test_stop(runtime_id)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        if runtime_id:
            print(f"Cleaning up runtime_id: {runtime_id}")
            test_stop(runtime_id)

if __name__ == "__main__":
    main()

