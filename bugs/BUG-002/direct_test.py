#!/usr/bin/env python3
"""
Direct test of BUG-002 by importing and calling evaluation logic directly.
"""

import sys
import os

# Add backend directory to path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

from alert_store import AlertStore
from store import MetricStore 
from models import AlertRuleIn, MetricIn

def test_bug_002_direct():
    """Test the bug by calling evaluation logic directly."""
    print("=== BUG-002 Direct Test ===")
    
    # Create stores
    metric_store = MetricStore()
    alert_store = AlertStore()
    
    # Step 1: Create alert rule
    print("\n1. Creating alert rule for 'cpu' > 80...")
    rule = alert_store.add_rule(AlertRuleIn(metric_name="cpu", operator="gt", threshold=80.0))
    print(f"Created rule {rule.id}, initial state: {rule.state}")
    
    # Step 2: Add metric that should trigger firing
    print("\n2. Adding metric 'cpu' = 95.0 (should trigger firing)...")
    metric_store.add(MetricIn(name="cpu", value=95.0))
    
    # Step 3: Evaluate - should transition to firing 
    print("\n3. Running evaluation...")
    transitions = alert_store.evaluate(metric_store)
    print(f"Transitions: {transitions}")
    print(f"Alert state after evaluation: {rule.state}")
    
    # Step 4: Delete the metric
    print("\n4. Deleting 'cpu' metrics...")
    deleted = metric_store.delete("cpu")
    print(f"Deleted {deleted} metrics")
    
    # Verify metrics are gone
    remaining = metric_store.by_name("cpu")
    print(f"Remaining 'cpu' metrics: {len(remaining)}")
    
    # Step 5: Evaluate again - should transition to ok
    print("\n5. Running evaluation after deletion...")
    transitions = alert_store.evaluate(metric_store)
    print(f"Transitions: {transitions}")
    print(f"Final alert state: {rule.state}")
    
    # Analysis
    print("\n=== ANALYSIS ===")
    if rule.state == "firing":
        print("🐛 BUG CONFIRMED: Alert stuck in firing state after metric deletion!")
        print("Expected: Alert should transition from 'firing' to 'ok'")
        print("Actual: Alert remains in 'firing' state")
        return True
    elif rule.state == "ok":
        print("✓ No bug detected: Alert correctly transitioned to 'ok' state")
        return False
    else:
        print(f"❓ Unexpected final state: {rule.state}")
        return False

if __name__ == "__main__":
    test_bug_002_direct()