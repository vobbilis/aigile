#!/usr/bin/env python3
"""
Simplified test to reproduce BUG-002 by directly calling alert evaluation methods.
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_bug_002_simplified():
    """Reproduce the bug scenario with immediate evaluation."""
    print("=== BUG-002 Simplified Reproduction ===")
    
    # Step 1: Create alert rule
    print("\n1. Creating alert rule for 'cpu' > 80...")
    alert_data = {"metric_name": "cpu", "operator": "gt", "threshold": 80.0}
    resp = requests.post(f"{BASE_URL}/alerts", json=alert_data)
    rule = resp.json()
    print(f"Created rule {rule['id']}, initial state: {rule['state']}")
    
    # Step 2: Submit metric that should trigger firing
    print("\n2. Submitting 'cpu' = 95.0 (should trigger firing)...")
    resp = requests.post(f"{BASE_URL}/metrics", json={"name": "cpu", "value": 95.0})
    print(f"Metric submitted: {resp.status_code}")
    
    # Step 3: Check alert state (evaluation happens automatically in background)
    print("\n3. Checking alert state after 12 seconds...")
    import time
    time.sleep(12)  # Wait for one evaluation cycle
    
    resp = requests.get(f"{BASE_URL}/alerts")
    alerts = resp.json()
    alert_after_metric = alerts[0]["state"]
    print(f"Alert state after metric submission: {alert_after_metric}")
    
    # Step 4: Delete the metric
    print("\n4. Deleting 'cpu' metrics...")
    resp = requests.delete(f"{BASE_URL}/metrics/cpu")
    deleted_count = resp.json()["deleted"]
    print(f"Deleted {deleted_count} metrics")
    
    # Verify deletion worked
    resp = requests.get(f"{BASE_URL}/metrics/cpu")
    print(f"Metrics check after deletion: {resp.status_code} (should be 404)")
    
    # Step 5: Wait for next evaluation and check state
    print("\n5. Waiting 12 seconds for next evaluation cycle...")
    time.sleep(12)
    
    resp = requests.get(f"{BASE_URL}/alerts")
    alerts = resp.json()
    final_state = alerts[0]["state"]
    print(f"Final alert state: {final_state}")
    
    # Analysis
    print("\n=== ANALYSIS ===")
    print(f"Step 3 - Alert state after metric: {alert_after_metric}")
    print(f"Step 5 - Alert state after deletion: {final_state}")
    
    if alert_after_metric == "firing" and final_state == "firing":
        print("🐛 BUG CONFIRMED: Alert stuck in firing state after metric deletion!")
        return True
    elif alert_after_metric == "firing" and final_state == "ok":  
        print("✓ No bug: Alert correctly transitioned from firing to ok")
        return False
    else:
        print(f"❓ Unexpected states: {alert_after_metric} -> {final_state}")
        return False

if __name__ == "__main__":
    try:
        resp = requests.get(f"{BASE_URL}/health")
        if resp.status_code == 200:
            print("✓ Server ready")
            test_bug_002_simplified()
        else:
            print("✗ Server not ready")
    except Exception as e:
        print(f"✗ Server connection failed: {e}")