#!/usr/bin/env python3
"""Minimal test of relegation logic without importing from app.py"""
print("Starting test...")

from collections import defaultdict

def calculate_win_pct(wins, losses, ties=0):
    total = wins + losses + ties
    if total == 0:
        return 0.0
    return (wins + 0.5 * ties) / total

# Mock data
stats = {
    'TeamA': {'wins': 5, 'losses': 9, 'ties': 0, 'division_wins': 2, 'division_losses': 4, 'points_for': 100, 'h2h': {}},
    'TeamB': {'wins': 5, 'losses': 9, 'ties': 0, 'division_wins': 2, 'division_losses': 4, 'points_for': 110, 'h2h': {}},
}

print("Testing calculate_win_pct...")
pct = calculate_win_pct(5, 9, 0)
print(f"  Result: {pct}")

print("Testing list operations...")
candidates = ['TeamA', 'TeamB']
best = max(candidates, key=lambda t: stats[t]['points_for'])
print(f"  Best: {best}")
candidates.remove(best)
print(f"  Remaining: {candidates}")

print("Test complete!")

