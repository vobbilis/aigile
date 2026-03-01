#!/usr/bin/env python3
"""
Test script to reproduce BUG-002: Alert rules continue evaluating against 
deleted metrics and stay in firing state.
"""

import time
import requests
import json

# API base URL 
BASE_URL = "http://localhost:8000"

def wait_for_server():
    """Wait for server to be ready.""" 
    for _ in range(10):
        try:
            resp = requests.get(f"{BASE_URL}/health")
            if resp.status_code == 200:
                print("✓ Server is ready")
                return True
        except requests.exceptions.ConnectionError:
            time.sleep(1)
    print("✗ Server not ready")
    return False

def test_bug_002():
    """Reproduce the bug scenario."""
    print("=== BUG-002 Reproduction Test ===")
    
    # Step 1: Create an alert rule
    print("\n1. Creating alert rule for 'cpu' > 80...")
    alert_data = {
        "metric_name": "cpu", 
        "operator": "gt",
        "threshold": 80.0
    }
    resp = requests.post(f"{BASE_URL}/alerts", json=alert_data)
    print(f"Alert creation: {resp.status_code}")
    rule = resp.json()
    rule_id = rule["id"]
    print(f"Created alert rule: {rule_id}, state: {rule['state']}")
    
    # Step 2: Submit metric that triggers the alert
    print("\n2. Submitting metric 'cpu' = 95.0 (should trigger firing)...")
    metric_data = {"name": "cpu", "value": 95.0}
    resp = requests.post(f"{BASE_URL}/metrics", json=metric_data)
    print(f"Metric submission: {resp.status_code}")
    
    # Step 3: Wait for evaluation cycle (10+ seconds)
    print("\n3. Waiting for alert evaluation cycle (15 seconds)...")
    time.sleep(15)
    
    # Check alert state
    resp = requests.get(f"{BASE_URL}/alerts")
    alerts = resp.json()
    current_state = alerts[0]["state"] if alerts else "unknown"
    print(f"Alert state after evaluation: {current_state}")
    
    # Step 4: Delete the metric
    print("\n4. Deleting 'cpu' metrics...")
    resp = requests.delete(f"{BASE_URL}/metrics/cpu")
    print(f"Metric deletion: {resp.status_code}, deleted: {resp.json()['deleted']}")
    
    # Verify metrics are gone
    try:
        resp = requests.get(f"{BASE_URL}/metrics/cpu")
        print(f"Metrics check: {resp.status_code} (should be 404)")
    except Exception as e:
        print(f"Metrics check: 404 (as expected)")
    
    # Step 5: Wait for another evaluation cycle
    print("\n5. Waiting for next evaluation cycle (15 seconds)...")
    time.sleep(15)
    
    # Step 6: Check final alert state
    resp = requests.get(f"{BASE_URL}/alerts")
    alerts = resp.json()
    final_state = alerts[0]["state"] if alerts else "unknown"
    print(f"Final alert state: {final_state}")
    
    # Analysis
    print("\n=== ANALYSIS ===")
    print(f"Expected behavior: Alert should transition from 'firing' to 'ok' after metrics deletion")
    print(f"Actual behavior: Alert state is '{final_state}'")
    
    if final_state == "firing":
        print("🐛 BUG CONFIRMED: Alert stuck in firing state after metric deletion")
        return True
    elif final_state == "ok":
        print("✓ No bug detected: Alert correctly transitioned to 'ok'")
        return False
    else:
        print(f"❓ Unexpected state: {final_state}")
        return False

if __name__ == "__main__":
    if wait_for_server():
        test_bug_002()
    else:
        print("Cannot reproduce - server not available")