#!/usr/bin/env python3
"""
Monte Carlo Simulation for Fantasy Football Playoff Scenarios

This module implements:
1. Home/away advantage calculation
2. Team performance distributions (neutral site adjusted)
3. Monte Carlo simulation of Week 14 outcomes
"""

import json
import numpy as np
from collections import defaultdict
import copy

# Load league data
with open('all_leagues_data.json') as f:
    ALL_LEAGUES = json.load(f)


def calculate_home_away_advantage(league_name):
    """
    Calculate league-wide home/away scoring averages and adjustment multipliers.
    
    Returns:
        dict with:
        - home_avg: average points for home teams
        - away_avg: average points for away teams
        - neutral_avg: midpoint (neutral site average)
        - home_to_neutral: multiplier to convert home scores to neutral
        - away_to_neutral: multiplier to convert away scores to neutral
    """
    league_data = ALL_LEAGUES[league_name]
    played_games = league_data.get('played_games', [])
    
    home_scores = []
    away_scores = []
    
    for game in played_games:
        home_scores.append(game['home_score'])
        away_scores.append(game['away_score'])
    
    home_avg = np.mean(home_scores)
    away_avg = np.mean(away_scores)
    neutral_avg = (home_avg + away_avg) / 2
    
    # Multipliers to convert to neutral site
    # home_score * home_to_neutral = neutral_score
    # away_score * away_to_neutral = neutral_score
    home_to_neutral = neutral_avg / home_avg if home_avg > 0 else 1.0
    away_to_neutral = neutral_avg / away_avg if away_avg > 0 else 1.0
    
    return {
        'home_avg': home_avg,
        'away_avg': away_avg,
        'neutral_avg': neutral_avg,
        'home_to_neutral': home_to_neutral,
        'away_to_neutral': away_to_neutral,
        'neutral_to_home': 1 / home_to_neutral if home_to_neutral > 0 else 1.0,
        'neutral_to_away': 1 / away_to_neutral if away_to_neutral > 0 else 1.0,
    }


def calculate_team_distributions(league_name, adjustments):
    """
    Calculate each team's neutral-site performance distribution (mean and sigma).
    
    For each team:
    - Convert all their scores to neutral-site equivalent
    - Calculate mean and standard deviation
    
    Returns:
        dict: {team_name: {'mean': float, 'sigma': float, 'neutral_scores': list}}
    """
    league_data = ALL_LEAGUES[league_name]
    played_games = league_data.get('played_games', [])
    teams = league_data['teams']
    
    # Collect scores for each team, noting if they were home or away
    team_scores = {team: [] for team in teams}
    
    for game in played_games:
        home_team = game['home_team']
        away_team = game['away_team']
        home_score = game['home_score']
        away_score = game['away_score']
        
        # Convert to neutral site scores
        if home_team in team_scores:
            neutral_home = home_score * adjustments['home_to_neutral']
            team_scores[home_team].append(neutral_home)
        
        if away_team in team_scores:
            neutral_away = away_score * adjustments['away_to_neutral']
            team_scores[away_team].append(neutral_away)
    
    # Calculate mean and sigma for each team
    distributions = {}
    for team, scores in team_scores.items():
        if len(scores) >= 2:
            distributions[team] = {
                'mean': np.mean(scores),
                'sigma': np.std(scores, ddof=1),  # Sample standard deviation
                'neutral_scores': scores,
                'n_games': len(scores),
            }
        else:
            # Fallback if not enough data
            distributions[team] = {
                'mean': adjustments['neutral_avg'],
                'sigma': 10.0,  # Default sigma
                'neutral_scores': scores,
                'n_games': len(scores),
            }
    
    return distributions


def simulate_game(away_dist, home_dist, adjustments, rng):
    """
    Simulate a single game between two teams.
    
    1. Generate neutral-site scores from each team's distribution
    2. Apply home/away adjustments
    3. Round to nearest 0.1
    
    Returns:
        tuple: (away_score, home_score)
    """
    # Generate neutral site scores
    away_neutral = rng.normal(away_dist['mean'], away_dist['sigma'])
    home_neutral = rng.normal(home_dist['mean'], home_dist['sigma'])
    
    # Ensure non-negative
    away_neutral = max(0, away_neutral)
    home_neutral = max(0, home_neutral)
    
    # Apply home/away adjustments
    away_score = away_neutral * adjustments['neutral_to_away']
    home_score = home_neutral * adjustments['neutral_to_home']
    
    # Round to nearest 0.1
    away_score = round(away_score, 1)
    home_score = round(home_score, 1)
    
    return away_score, home_score


def simulate_week14(league_name, distributions, adjustments, rng):
    """
    Simulate all Week 14 games and return the outcomes.
    
    Returns:
        list of dicts with game results
    """
    league_data = ALL_LEAGUES[league_name]
    matchups = league_data['week14_matchups']
    
    results = []
    for matchup in matchups:
        away_team = matchup['away_team']
        home_team = matchup['home_team']
        
        away_dist = distributions[away_team]
        home_dist = distributions[home_team]
        
        away_score, home_score = simulate_game(away_dist, home_dist, adjustments, rng)
        
        results.append({
            'away_team': away_team,
            'home_team': home_team,
            'away_score': away_score,
            'home_score': home_score,
            'winner': away_team if away_score > home_score else home_team,
            'is_division_game': matchup['is_division_game'],
        })
    
    return results


# Import playoff determination functions from app.py
def get_team_division(team, divisions):
    for div, teams in divisions.items():
        if team in teams:
            return div
    return None


def calculate_win_pct(wins, losses, ties=0):
    total = wins + losses + ties
    if total == 0:
        return 0.0
    return (wins + 0.5 * ties) / total


def apply_simulation_results(base_stats, game_results, divisions):
    """
    Apply simulated game results to create updated stats.
    """
    new_stats = copy.deepcopy(base_stats)
    
    for game in game_results:
        away = game['away_team']
        home = game['home_team']
        is_div = game['is_division_game']
        
        if game['away_score'] > game['home_score']:
            # Away team wins
            new_stats[away]['wins'] += 1
            new_stats[home]['losses'] += 1
            if is_div:
                new_stats[away]['division_wins'] += 1
                new_stats[home]['division_losses'] += 1
        else:
            # Home team wins (ties go to home in this simple model)
            new_stats[home]['wins'] += 1
            new_stats[away]['losses'] += 1
            if is_div:
                new_stats[home]['division_wins'] += 1
                new_stats[away]['division_losses'] += 1
    
    return new_stats


def run_monte_carlo(league_name, n_simulations=10000, seed=None):
    """
    Run Monte Carlo simulation for playoff scenarios.
    
    Returns:
        dict with:
        - team_results: {team: {playoff_pct, seed_pcts: {1: %, 2: %, ...}}}
        - adjustments: home/away adjustment data
        - distributions: team distribution data
    """
    # Import playoff determination from app
    from app import determine_playoff_teams, determine_relegation_teams
    
    league_data = ALL_LEAGUES[league_name]
    teams = league_data['teams']
    divisions = league_data['divisions']
    stats = league_data['stats']
    has_relegation = league_data.get('has_relegation', False)
    
    # Step 1: Calculate home/away adjustments
    adjustments = calculate_home_away_advantage(league_name)
    print(f"\n=== {league_name} Home/Away Analysis ===")
    print(f"Home average: {adjustments['home_avg']:.2f}")
    print(f"Away average: {adjustments['away_avg']:.2f}")
    print(f"Neutral average: {adjustments['neutral_avg']:.2f}")
    print(f"Home advantage: +{(adjustments['neutral_to_home'] - 1) * 100:.1f}%")
    print(f"Away disadvantage: {(adjustments['neutral_to_away'] - 1) * 100:.1f}%")
    
    # Step 2: Calculate team distributions
    distributions = calculate_team_distributions(league_name, adjustments)
    print(f"\n=== Team Distributions (Neutral Site) ===")
    for team in sorted(teams, key=lambda t: -distributions[t]['mean']):
        d = distributions[team]
        print(f"{team}: μ={d['mean']:.1f}, σ={d['sigma']:.1f}")
    
    # Step 3: Run Monte Carlo simulations
    rng = np.random.default_rng(seed)
    
    # Track results
    playoff_counts = {team: 0 for team in teams}
    seed_counts = {team: {i: 0 for i in range(1, 7)} for team in teams}
    
    # Track relegation for leagues with it
    relegation_counts = {team: 0 for team in teams}
    relegation_seed_counts = {team: {i: 0 for i in range(1, 5)} for team in teams}  # Seeds 1-4
    
    print(f"\n=== Running {n_simulations:,} simulations ===")
    
    for sim in range(n_simulations):
        if (sim + 1) % 2000 == 0:
            print(f"  Completed {sim + 1:,} simulations...")
        
        # Simulate Week 14
        game_results = simulate_week14(league_name, distributions, adjustments, rng)
        
        # Apply results to get final standings
        final_stats = apply_simulation_results(stats, game_results, divisions)
        
        # Determine playoff teams
        playoff_teams = determine_playoff_teams(final_stats, teams, divisions)
        
        # Record playoff results
        for p in playoff_teams:
            team = p['team']
            seed = p['seed']
            playoff_counts[team] += 1
            if seed <= 6:
                seed_counts[team][seed] += 1
        
        # Track relegation if applicable
        if has_relegation:
            relegation_teams = determine_relegation_teams(final_stats, playoff_teams, teams, divisions)
            for r in relegation_teams:
                team = r['team']
                seed = r['seed']
                relegation_counts[team] += 1
                if seed <= 4:
                    relegation_seed_counts[team][seed] += 1
    
    # Calculate percentages
    results = {}
    for team in teams:
        playoff_pct = (playoff_counts[team] / n_simulations) * 100
        seed_pcts = {seed: (count / n_simulations) * 100 
                     for seed, count in seed_counts[team].items()}
        bye_pct = seed_pcts[1] + seed_pcts[2]  # Seeds 1-2 get bye
        
        result = {
            'playoff_pct': round(playoff_pct, 1),
            'bye_pct': round(bye_pct, 1),
            'seed_pcts': {k: round(v, 1) for k, v in seed_pcts.items()},
        }
        
        if has_relegation:
            relegation_pct = (relegation_counts[team] / n_simulations) * 100
            releg_seed_pcts = {seed: (count / n_simulations) * 100 
                              for seed, count in relegation_seed_counts[team].items()}
            result['relegation_pct'] = round(relegation_pct, 1)
            result['relegation_seed_pcts'] = {k: round(v, 1) for k, v in releg_seed_pcts.items()}
        
        results[team] = result
    
    # Print results
    print(f"\n=== Playoff Probabilities ===")
    print(f"{'Team':35s} | {'Playoff':>7s} | {'Bye':>6s} | {'#1':>6s} | {'#2':>6s} | {'#3':>6s} | {'#4':>6s} | {'#5':>6s} | {'#6':>6s}")
    print("-" * 110)
    sorted_teams = sorted(teams, key=lambda t: -results[t]['playoff_pct'])
    for team in sorted_teams:
        r = results[team]
        seeds_str = ' | '.join([f"{r['seed_pcts'][i]:>5.1f}%" for i in range(1, 7)])
        print(f"{team:35s} | {r['playoff_pct']:>6.1f}% | {r['bye_pct']:>5.1f}% | {seeds_str}")
    
    if has_relegation:
        print(f"\n=== Relegation Probabilities ===")
        print(f"{'Team':35s} | {'Releg':>7s} | {'#1':>6s} | {'#2':>6s} | {'#3':>6s} | {'#4':>6s}")
        print("-" * 80)
        sorted_by_releg = sorted(teams, key=lambda t: -results[t].get('relegation_pct', 0))
        for team in sorted_by_releg:
            r = results[team]
            if r.get('relegation_pct', 0) > 0:
                releg_seeds = r.get('relegation_seed_pcts', {})
                seeds_str = ' | '.join([f"{releg_seeds.get(i, 0):>5.1f}%" for i in range(1, 5)])
                print(f"{team:35s} | {r['relegation_pct']:>6.1f}% | {seeds_str}")
    
    return {
        'team_results': results,
        'adjustments': adjustments,
        'distributions': {t: {'mean': d['mean'], 'sigma': d['sigma']} 
                          for t, d in distributions.items()},
        'n_simulations': n_simulations,
        'has_relegation': has_relegation,
    }


def run_all_leagues(n_simulations=10000, seed=42):
    """Run Monte Carlo for all leagues and save results."""
    all_results = {}
    
    for league_name in ['WFFL', 'DFFL', 'FFPL']:
        print(f"\n{'='*60}")
        print(f"  Running Monte Carlo for {league_name}")
        print(f"{'='*60}")
        results = run_monte_carlo(league_name, n_simulations=n_simulations, seed=seed)
        all_results[league_name] = results
    
    # Save all results
    with open('monte_carlo_results.json', 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n✅ All results saved to monte_carlo_results.json")
    return all_results


if __name__ == "__main__":
    run_all_leagues(n_simulations=10000, seed=42)

