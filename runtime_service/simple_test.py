#!/usr/bin/env python3
"""Simple test to verify runtime service basic functionality"""

import requests
import json

BASE_URL = "http://localhost:8005"

print("Testing Runtime Service...")
print()

# Test 1: Health check
print("1. Health check...")
resp = requests.get(f"{BASE_URL}/health")
print(f"   Status: {resp.status_code}")
print(f"   Response: {resp.json()}")
print()

# Test 2: Create environment (airline, task 0)
print("2. Creating tau environment (airline, task_index=0)...")
print("   ⏳ This may take 1-3 minutes...")

params = {
    "env_name": "airline",
    "task_index": 0
}

try:
    resp = requests.post(
        f"{BASE_URL}/create",
        json={
            "env_type": "tau",
            "params": json.dumps(params)
        },
        timeout=300
    )
    print(f"   Status: {resp.status_code}")
    
    if resp.status_code == 200:
        data = resp.json()
        runtime_id = data["runtime_id"]
        meta_info = json.loads(data["meta_info"])
        
        print(f"   ✅ Environment created!")
        print(f"   Runtime ID: {runtime_id}")
        print(f"   Initial question: {meta_info['initial_question'][:80]}...")
        print()
        
        # Test 3: Ping
        print("3. Pinging environment...")
        resp = requests.post(f"{BASE_URL}/ping", json={"runtime_id": runtime_id})
        print(f"   Status: {resp.status_code}")
        print(f"   Response: {resp.json()}")
        print()
        
        # Test 4: Step
        print("4. Stepping environment (search_direct_flight)...")
        step_params = {
            "name": "search_direct_flight",
            "arguments": {
                "departure_airport": "JFK",
                "arrival_airport": "LAX",
                "departure_date": "2024-01-15"
            }
        }
        
        resp = requests.post(
            f"{BASE_URL}/step",
            json={
                "runtime_id": runtime_id,
                "params": json.dumps(step_params)
            },
            timeout=120
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            result = resp.json()["result"]
            print(f"   Result: {result[:150]}...")
        else:
            print(f"   Error: {resp.text}")
        print()
        
        # Test 5: Reward
        print("5. Getting reward...")
        resp = requests.post(
            f"{BASE_URL}/reward",
            json={
                "runtime_id": runtime_id,
                "params": "{}"
            }
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            reward = resp.json()["reward"]
            print(f"   Reward: {reward}")
        print()
        
        # Test 6: Stop
        print("6. Stopping environment...")
        resp = requests.post(f"{BASE_URL}/stop", json={"runtime_id": runtime_id})
        print(f"   Status: {resp.status_code}")
        print(f"   Response: {resp.json()}")
        print()
        
        print("✅ All tests passed!")
        
    else:
        print(f"   ❌ Failed: {resp.text}")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

