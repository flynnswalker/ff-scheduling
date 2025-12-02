#!/usr/bin/env python3
"""
Fantasy Football Playoff Scenario Analyzer for FFPL.

Playoff Format:
- 6 teams make championship playoffs
- 3 division winners + 3 wild cards
- Top 2 seeds get first-round bye
- 3-week playoff

Relegation Format:
- Bottom 4 teams play in relegation playoffs
- Loser of relegation bracket gets relegated (doesn't play next season!)
- Selected from bottom up: worst record first, tiebreaker WINNER stays safe

Seeding:
- Seeds 1-3: Division winners (ordered by Wild Card tiebreakers)
- Seeds 4-6: Wild cards (ordered by Wild Card tiebreakers)

Tiebreaker Rules (from https://www.dougin.com/ffl/FFL.cfm?FID=ffl_tie.htm):

Division Tiebreaker (to order 1-4 within division):
1. Head-to-Head Record
2. Division Record
3. Total Points in H2H Games
4. Total Points in All Games
5. Matrix Rank
6. Coin Toss

Wild Card Tiebreaker (for WC selection and all seeding):
1. Head-to-Head Record
2. Strength of Schedule (opponents' combined win pct)
3. Total Points in All Games
4. Matrix Rank
5. Coin Toss
"""

import json
import copy
from itertools import product
from collections import defaultdict

# Load data
with open('full_history.json') as f:
    DATA = json.load(f)

TEAMS = DATA['teams']
DIVISIONS = DATA['divisions']
STATS = DATA['stats']
WEEK14_MATCHUPS = DATA['week14_matchups']
MATRIX_RANKS = DATA['matrix_ranks']


def get_team_division(team):
    """Get division for a team."""
    for div, teams in DIVISIONS.items():
        if team in teams:
            return div
    return None


def calculate_win_pct(wins, losses, ties=0):
    """Calculate winning percentage."""
    total = wins + losses + ties
    if total == 0:
        return 0.0
    return (wins + 0.5 * ties) / total


def get_h2h_record(stats, team1, team2):
    """Get head-to-head record of team1 vs team2."""
    h2h = stats[team1]['h2h'][team2]
    return h2h['wins'], h2h['losses'], h2h['ties']


def get_h2h_record_vs_group(stats, team, opponents):
    """Get combined H2H record vs a group of opponents."""
    wins = losses = ties = 0
    for opp in opponents:
        if opp != team:
            h2h = stats[team]['h2h'].get(opp, {'wins': 0, 'losses': 0, 'ties': 0})
            wins += h2h['wins']
            losses += h2h['losses']
            ties += h2h['ties']
    return wins, losses, ties


def get_h2h_points_vs_group(stats, team, opponents):
    """Get total points scored in H2H games vs a group of opponents."""
    points_for = 0
    for opp in opponents:
        if opp != team:
            h2h = stats[team]['h2h'].get(opp, {'points_for': 0})
            points_for += h2h['points_for']
    return points_for


def calculate_strength_of_schedule(stats, team):
    """Calculate strength of schedule as combined win pct of all opponents faced."""
    total_opp_wins = 0
    total_opp_losses = 0
    total_opp_ties = 0
    
    for opp in TEAMS:
        if opp != team:
            h2h = stats[team]['h2h'].get(opp, {'wins': 0, 'losses': 0, 'ties': 0})
            games_vs_opp = h2h['wins'] + h2h['losses'] + h2h['ties']
            
            if games_vs_opp > 0:
                opp_stats = stats[opp]
                total_opp_wins += opp_stats['wins'] * games_vs_opp
                total_opp_losses += opp_stats['losses'] * games_vs_opp
                total_opp_ties += opp_stats['ties'] * games_vs_opp
    
    return calculate_win_pct(total_opp_wins, total_opp_losses, total_opp_ties)


def break_tie_division(stats, tied_teams, h2h_points_override=None):
    """Break tie for division ranking using Division Tiebreaker rules."""
    if len(tied_teams) == 1:
        return tied_teams
    
    if len(tied_teams) == 2:
        return _break_tie_division_two(stats, tied_teams, h2h_points_override)
    
    return _break_tie_division_multi(stats, tied_teams, h2h_points_override)


def _break_tie_division_two(stats, tied_teams, h2h_points_override=None):
    """Break tie between exactly 2 teams for division ranking."""
    t1, t2 = tied_teams
    
    # 1. Head-to-Head Record
    w1, l1, tie1 = get_h2h_record(stats, t1, t2)
    w2, l2, tie2 = get_h2h_record(stats, t2, t1)
    
    if w1 > w2:
        return [t1, t2]
    elif w2 > w1:
        return [t2, t1]
    
    # 2. Division Record
    div1_pct = calculate_win_pct(stats[t1]['division_wins'], stats[t1]['division_losses'], stats[t1]['division_ties'])
    div2_pct = calculate_win_pct(stats[t2]['division_wins'], stats[t2]['division_losses'], stats[t2]['division_ties'])
    
    if div1_pct > div2_pct:
        return [t1, t2]
    elif div2_pct > div1_pct:
        return [t2, t1]
    
    # 3. Total Points in H2H Games
    if h2h_points_override and (t1, t2) in h2h_points_override:
        h2h_pts1, h2h_pts2 = h2h_points_override[(t1, t2)]
    else:
        h2h_pts1 = stats[t1]['h2h'][t2]['points_for']
        h2h_pts2 = stats[t2]['h2h'][t1]['points_for']
    
    if h2h_pts1 > h2h_pts2:
        return [t1, t2]
    elif h2h_pts2 > h2h_pts1:
        return [t2, t1]
    
    # 4. Total Points in All Games
    if stats[t1]['points_for'] > stats[t2]['points_for']:
        return [t1, t2]
    elif stats[t2]['points_for'] > stats[t1]['points_for']:
        return [t2, t1]
    
    # 5. Matrix Rank (lower is better)
    if stats[t1]['matrix_rank'] < stats[t2]['matrix_rank']:
        return [t1, t2]
    elif stats[t2]['matrix_rank'] < stats[t1]['matrix_rank']:
        return [t2, t1]
    
    # 6. Coin Toss
    return sorted([t1, t2])


def _break_tie_division_multi(stats, tied_teams, h2h_points_override=None):
    """Break tie among 3+ teams for division ranking."""
    remaining = list(tied_teams)
    result = []
    
    while len(remaining) > 1:
        # 1. Head-to-Head Record among tied teams
        h2h_records = {}
        for team in remaining:
            w, l, t = get_h2h_record_vs_group(stats, team, remaining)
            h2h_records[team] = calculate_win_pct(w, l, t)
        
        best_pct = max(h2h_records.values())
        best_teams = [t for t in remaining if h2h_records[t] == best_pct]
        
        if len(best_teams) < len(remaining):
            if len(best_teams) == 1:
                result.append(best_teams[0])
                remaining.remove(best_teams[0])
            else:
                ordered_best = _break_tie_division_multi(stats, best_teams, h2h_points_override)
                result.extend(ordered_best)
                for t in ordered_best:
                    remaining.remove(t)
            continue
        
        # 2. Division Record
        div_records = {}
        for team in remaining:
            div_records[team] = calculate_win_pct(
                stats[team]['division_wins'],
                stats[team]['division_losses'],
                stats[team]['division_ties']
            )
        
        best_div = max(div_records.values())
        best_teams = [t for t in remaining if div_records[t] == best_div]
        
        if len(best_teams) < len(remaining):
            if len(best_teams) == 1:
                result.append(best_teams[0])
                remaining.remove(best_teams[0])
            else:
                ordered_best = _break_tie_division_multi(stats, best_teams, h2h_points_override)
                result.extend(ordered_best)
                for t in ordered_best:
                    remaining.remove(t)
            continue
        
        # 3. Total Points in H2H Games
        h2h_points = {}
        for team in remaining:
            h2h_points[team] = get_h2h_points_vs_group(stats, team, remaining)
        
        best_pts = max(h2h_points.values())
        best_teams = [t for t in remaining if h2h_points[t] == best_pts]
        
        if len(best_teams) < len(remaining):
            if len(best_teams) == 1:
                result.append(best_teams[0])
                remaining.remove(best_teams[0])
            else:
                ordered_best = _break_tie_division_multi(stats, best_teams, h2h_points_override)
                result.extend(ordered_best)
                for t in ordered_best:
                    remaining.remove(t)
            continue
        
        # 4. Total Points in All Games
        total_points = {t: stats[t]['points_for'] for t in remaining}
        best_pts = max(total_points.values())
        best_teams = [t for t in remaining if total_points[t] == best_pts]
        
        if len(best_teams) < len(remaining):
            if len(best_teams) == 1:
                result.append(best_teams[0])
                remaining.remove(best_teams[0])
            else:
                ordered_best = _break_tie_division_multi(stats, best_teams, h2h_points_override)
                result.extend(ordered_best)
                for t in ordered_best:
                    remaining.remove(t)
            continue
        
        # 5. Matrix Rank
        matrix_ranks = {t: stats[t]['matrix_rank'] for t in remaining}
        best_rank = min(matrix_ranks.values())
        best_teams = [t for t in remaining if matrix_ranks[t] == best_rank]
        
        if len(best_teams) == 1:
            result.append(best_teams[0])
            remaining.remove(best_teams[0])
            continue
        
        # 6. Coin toss
        result.extend(sorted(remaining))
        remaining = []
    
    if remaining:
        result.extend(remaining)
    
    return result


def break_tie_wildcard(stats, tied_teams):
    """
    Break tie for wild card / seeding using Wild Card Tiebreaker rules.
    Returns teams in order from BEST to WORST.
    
    IMPORTANT: For teams in the SAME division, use Division Tiebreaker
    (which includes division record) rather than pure Wild Card rules.
    
    The process:
    1. First, order teams within their own divisions using Division Tiebreaker
    2. Then, compare across divisions using overall record, SOS, points, etc.
    """
    if len(tied_teams) == 1:
        return tied_teams
    
    # First, group teams by division
    by_division = defaultdict(list)
    for team in tied_teams:
        div = get_team_division(team)
        by_division[div].append(team)
    
    # If all teams are in the same division, use division tiebreaker
    if len(by_division) == 1:
        return break_tie_division(stats, tied_teams)
    
    # Teams span multiple divisions
    # Step 1: Order teams WITHIN each division using division tiebreaker
    ordered_by_div = {}
    for div, teams in by_division.items():
        if len(teams) > 1:
            ordered_by_div[div] = break_tie_division(stats, teams)
        else:
            ordered_by_div[div] = teams
    
    # Step 2: Now compare across divisions
    # Take the best remaining team from each division and compare using WC tiebreaker
    # This preserves within-division ordering
    
    result = []
    remaining_by_div = {div: list(teams) for div, teams in ordered_by_div.items()}
    
    while sum(len(teams) for teams in remaining_by_div.values()) > 0:
        # Get the "best" (first) remaining team from each division
        candidates = []
        for div, teams in remaining_by_div.items():
            if teams:
                candidates.append(teams[0])
        
        if len(candidates) == 1:
            # Only one division has teams left
            team = candidates[0]
            result.append(team)
            div = get_team_division(team)
            remaining_by_div[div].pop(0)
        else:
            # Compare candidates across divisions using WC tiebreaker
            # (H2H among candidates, then SOS, then points, etc.)
            best = _compare_cross_division(stats, candidates)
            result.append(best)
            div = get_team_division(best)
            remaining_by_div[div].pop(0)
    
    return result


def _compare_cross_division(stats, candidates):
    """
    Compare teams from different divisions to find the best one.
    Uses Wild Card tiebreaker rules: H2H, SOS, Points, Matrix Rank.
    Returns the single best team.
    """
    if len(candidates) == 1:
        return candidates[0]
    
    if len(candidates) == 2:
        ordered = _break_tie_wildcard_two(stats, candidates)
        return ordered[0]
    
    # For 3+ candidates, use multi-team logic
    remaining = list(candidates)
    
    # 1. H2H among candidates
    h2h_records = {}
    for team in remaining:
        w, l, t = get_h2h_record_vs_group(stats, team, remaining)
        h2h_records[team] = calculate_win_pct(w, l, t)
    
    best_pct = max(h2h_records.values())
    best_teams = [t for t in remaining if h2h_records[t] == best_pct]
    
    if len(best_teams) == 1:
        return best_teams[0]
    
    remaining = best_teams
    
    # 2. Strength of Schedule
    sos = {t: calculate_strength_of_schedule(stats, t) for t in remaining}
    best_sos = max(sos.values())
    best_teams = [t for t in remaining if sos[t] == best_sos]
    
    if len(best_teams) == 1:
        return best_teams[0]
    
    remaining = best_teams
    
    # 3. Total Points
    points = {t: stats[t]['points_for'] for t in remaining}
    best_pts = max(points.values())
    best_teams = [t for t in remaining if points[t] == best_pts]
    
    if len(best_teams) == 1:
        return best_teams[0]
    
    remaining = best_teams
    
    # 4. Matrix Rank
    ranks = {t: stats[t]['matrix_rank'] for t in remaining}
    best_rank = min(ranks.values())
    best_teams = [t for t in remaining if ranks[t] == best_rank]
    
    if len(best_teams) == 1:
        return best_teams[0]
    
    # 5. Coin toss (alphabetical)
    return sorted(remaining)[0]


def _break_tie_wildcard_two(stats, tied_teams):
    """Break tie between exactly 2 teams for wild card."""
    t1, t2 = tied_teams
    
    # 1. Head-to-Head Record
    w1, l1, _ = get_h2h_record(stats, t1, t2)
    w2, l2, _ = get_h2h_record(stats, t2, t1)
    
    if w1 > w2:
        return [t1, t2]
    elif w2 > w1:
        return [t2, t1]
    
    # 2. Strength of Schedule
    sos1 = calculate_strength_of_schedule(stats, t1)
    sos2 = calculate_strength_of_schedule(stats, t2)
    
    if sos1 > sos2:
        return [t1, t2]
    elif sos2 > sos1:
        return [t2, t1]
    
    # 3. Total Points in All Games
    if stats[t1]['points_for'] > stats[t2]['points_for']:
        return [t1, t2]
    elif stats[t2]['points_for'] > stats[t1]['points_for']:
        return [t2, t1]
    
    # 4. Matrix Rank
    if stats[t1]['matrix_rank'] < stats[t2]['matrix_rank']:
        return [t1, t2]
    elif stats[t2]['matrix_rank'] < stats[t1]['matrix_rank']:
        return [t2, t1]
    
    # 5. Coin toss
    return sorted([t1, t2])


def _break_tie_wildcard_multi(stats, tied_teams):
    """Break tie among 3+ teams for wild card."""
    remaining = list(tied_teams)
    result = []
    
    while len(remaining) > 1:
        h2h_records = {}
        for team in remaining:
            w, l, t = get_h2h_record_vs_group(stats, team, remaining)
            h2h_records[team] = calculate_win_pct(w, l, t)
        
        best_pct = max(h2h_records.values())
        best_teams = [t for t in remaining if h2h_records[t] == best_pct]
        
        if len(best_teams) < len(remaining):
            if len(best_teams) == 1:
                result.append(best_teams[0])
                remaining.remove(best_teams[0])
            else:
                ordered_best = _break_tie_wildcard_multi(stats, best_teams)
                result.extend(ordered_best)
                for t in ordered_best:
                    remaining.remove(t)
            continue
        
        sos = {t: calculate_strength_of_schedule(stats, t) for t in remaining}
        best_sos = max(sos.values())
        best_teams = [t for t in remaining if sos[t] == best_sos]
        
        if len(best_teams) < len(remaining):
            if len(best_teams) == 1:
                result.append(best_teams[0])
                remaining.remove(best_teams[0])
            else:
                ordered_best = _break_tie_wildcard_multi(stats, best_teams)
                result.extend(ordered_best)
                for t in ordered_best:
                    remaining.remove(t)
            continue
        
        total_points = {t: stats[t]['points_for'] for t in remaining}
        best_pts = max(total_points.values())
        best_teams = [t for t in remaining if total_points[t] == best_pts]
        
        if len(best_teams) < len(remaining):
            if len(best_teams) == 1:
                result.append(best_teams[0])
                remaining.remove(best_teams[0])
            else:
                ordered_best = _break_tie_wildcard_multi(stats, best_teams)
                result.extend(ordered_best)
                for t in ordered_best:
                    remaining.remove(t)
            continue
        
        matrix_ranks = {t: stats[t]['matrix_rank'] for t in remaining}
        best_rank = min(matrix_ranks.values())
        best_teams = [t for t in remaining if matrix_ranks[t] == best_rank]
        
        if len(best_teams) == 1:
            result.append(best_teams[0])
            remaining.remove(best_teams[0])
            continue
        
        result.extend(sorted(remaining))
        remaining = []
    
    if remaining:
        result.extend(remaining)
    
    return result


def _break_tie_wildcard_multi_with_division(stats, tied_teams, ordered_by_div):
    """
    Break tie among 3+ teams for wild card, respecting division ordering.
    
    For teams in the same division, their relative order is already determined
    by the division tiebreaker. This function ensures that ordering is preserved
    while also comparing across divisions.
    """
    remaining = list(tied_teams)
    result = []
    
    while len(remaining) > 1:
        # Check if any same-division pairs exist in remaining
        # If so, we can use their pre-determined order
        
        # First, try H2H among all remaining teams
        h2h_records = {}
        for team in remaining:
            w, l, t = get_h2h_record_vs_group(stats, team, remaining)
            h2h_records[team] = calculate_win_pct(w, l, t)
        
        best_pct = max(h2h_records.values())
        worst_pct = min(h2h_records.values())
        best_teams = [t for t in remaining if h2h_records[t] == best_pct]
        worst_teams = [t for t in remaining if h2h_records[t] == worst_pct]
        
        # Check if we can separate based on H2H
        if len(best_teams) < len(remaining):
            if len(best_teams) == 1:
                result.append(best_teams[0])
                remaining.remove(best_teams[0])
            else:
                # Recursively handle the best teams
                ordered_best = break_tie_wildcard(stats, best_teams)
                result.extend(ordered_best)
                for t in ordered_best:
                    remaining.remove(t)
            continue
        
        # H2H didn't separate - check division record for same-division teams
        # Group remaining by division
        remaining_by_div = defaultdict(list)
        for team in remaining:
            remaining_by_div[get_team_division(team)].append(team)
        
        # For any division with multiple teams, use division record to separate
        separated = False
        for div, div_teams in remaining_by_div.items():
            if len(div_teams) > 1:
                # Use division record to order these teams
                div_records = {}
                for team in div_teams:
                    div_records[team] = calculate_win_pct(
                        stats[team]['division_wins'],
                        stats[team]['division_losses'],
                        stats[team]['division_ties']
                    )
                
                best_div_pct = max(div_records.values())
                best_div_teams = [t for t in div_teams if div_records[t] == best_div_pct]
                
                if len(best_div_teams) < len(div_teams):
                    # We can separate within this division!
                    # Add the best team(s) from this division first
                    if len(best_div_teams) == 1:
                        result.append(best_div_teams[0])
                        remaining.remove(best_div_teams[0])
                    else:
                        ordered_best = break_tie_division(stats, best_div_teams)
                        result.extend(ordered_best)
                        for t in ordered_best:
                            remaining.remove(t)
                    separated = True
                    break
        
        if separated:
            continue
        
        # Try strength of schedule
        sos = {t: calculate_strength_of_schedule(stats, t) for t in remaining}
        best_sos = max(sos.values())
        best_teams = [t for t in remaining if sos[t] == best_sos]
        
        if len(best_teams) < len(remaining):
            if len(best_teams) == 1:
                result.append(best_teams[0])
                remaining.remove(best_teams[0])
            else:
                ordered_best = break_tie_wildcard(stats, best_teams)
                result.extend(ordered_best)
                for t in ordered_best:
                    remaining.remove(t)
            continue
        
        # Try total points
        total_points = {t: stats[t]['points_for'] for t in remaining}
        best_pts = max(total_points.values())
        best_teams = [t for t in remaining if total_points[t] == best_pts]
        
        if len(best_teams) < len(remaining):
            if len(best_teams) == 1:
                result.append(best_teams[0])
                remaining.remove(best_teams[0])
            else:
                ordered_best = break_tie_wildcard(stats, best_teams)
                result.extend(ordered_best)
                for t in ordered_best:
                    remaining.remove(t)
            continue
        
        # Try matrix rank
        matrix_ranks = {t: stats[t]['matrix_rank'] for t in remaining}
        best_rank = min(matrix_ranks.values())
        best_teams = [t for t in remaining if matrix_ranks[t] == best_rank]
        
        if len(best_teams) == 1:
            result.append(best_teams[0])
            remaining.remove(best_teams[0])
            continue
        
        # Coin toss
        result.extend(sorted(remaining))
        remaining = []
    
    if remaining:
        result.extend(remaining)
    
    return result


def rank_division(stats, division, h2h_points_override=None):
    """Rank teams within a division 1-4."""
    teams = DIVISIONS[division]
    
    by_record = defaultdict(list)
    for team in teams:
        record = (stats[team]['wins'], stats[team]['losses'], stats[team]['ties'])
        by_record[record].append(team)
    
    sorted_records = sorted(by_record.keys(), key=lambda r: (-r[0], r[1], r[2]))
    
    ranking = []
    for record in sorted_records:
        tied_teams = by_record[record]
        if len(tied_teams) == 1:
            ranking.extend(tied_teams)
        else:
            ranking.extend(break_tie_division(stats, tied_teams, h2h_points_override))
    
    return ranking


def determine_playoff_teams(stats, h2h_points_override=None):
    """Determine the 6 playoff teams and their seeding."""
    division_rankings = {}
    for div in DIVISIONS:
        division_rankings[div] = rank_division(stats, div, h2h_points_override)
    
    division_winners = [division_rankings[div][0] for div in ['O', 'W', 'D']]
    non_winners = [t for t in TEAMS if t not in division_winners]
    
    by_record = defaultdict(list)
    for team in non_winners:
        record = (stats[team]['wins'], stats[team]['losses'], stats[team]['ties'])
        by_record[record].append(team)
    
    sorted_records = sorted(by_record.keys(), key=lambda r: (-r[0], r[1], r[2]))
    
    wild_cards = []
    for record in sorted_records:
        if len(wild_cards) >= 3:
            break
        
        tied_teams = by_record[record]
        spots_remaining = 3 - len(wild_cards)
        
        if len(tied_teams) <= spots_remaining:
            wild_cards.extend(tied_teams)
        else:
            ordered = break_tie_wildcard(stats, tied_teams)
            wild_cards.extend(ordered[:spots_remaining])
    
    winner_records = defaultdict(list)
    for team in division_winners:
        record = (stats[team]['wins'], stats[team]['losses'], stats[team]['ties'])
        winner_records[record].append(team)
    
    sorted_winner_records = sorted(winner_records.keys(), key=lambda r: (-r[0], r[1], r[2]))
    
    seeded_winners = []
    for record in sorted_winner_records:
        tied = winner_records[record]
        if len(tied) == 1:
            seeded_winners.extend(tied)
        else:
            seeded_winners.extend(break_tie_wildcard(stats, tied))
    
    wc_records = defaultdict(list)
    for team in wild_cards:
        record = (stats[team]['wins'], stats[team]['losses'], stats[team]['ties'])
        wc_records[record].append(team)
    
    sorted_wc_records = sorted(wc_records.keys(), key=lambda r: (-r[0], r[1], r[2]))
    
    seeded_wildcards = []
    for record in sorted_wc_records:
        tied = wc_records[record]
        if len(tied) == 1:
            seeded_wildcards.extend(tied)
        else:
            seeded_wildcards.extend(break_tie_wildcard(stats, tied))
    
    playoff_teams = []
    for i, team in enumerate(seeded_winners):
        playoff_teams.append((i + 1, team, True))
    for i, team in enumerate(seeded_wildcards):
        playoff_teams.append((i + 4, team, False))
    
    return playoff_teams


def determine_relegation_teams(stats, playoff_teams):
    """
    Determine the 4 relegation playoff teams.
    
    Selection is from BOTTOM UP:
    - Start with worst record, they're in relegation
    - If tie, tiebreaker WINNER is SAFE (stays out of relegation)
    - Continue until 4 teams selected
    
    Returns: list of (seed, team) tuples, seed 1 = worst team
    """
    # Get teams NOT in championship playoffs
    playoff_team_names = [team for _, team, _ in playoff_teams]
    non_playoff_teams = [t for t in TEAMS if t not in playoff_team_names]
    
    # Group by record
    by_record = defaultdict(list)
    for team in non_playoff_teams:
        record = (stats[team]['wins'], stats[team]['losses'], stats[team]['ties'])
        by_record[record].append(team)
    
    # Sort records from WORST to BEST (ascending wins, descending losses)
    sorted_records = sorted(by_record.keys(), key=lambda r: (r[0], -r[1], -r[2]))
    
    # Select 4 teams for relegation, starting from worst
    relegation_teams = []
    
    for record in sorted_records:
        if len(relegation_teams) >= 4:
            break
        
        tied_teams = by_record[record]
        spots_remaining = 4 - len(relegation_teams)
        
        if len(tied_teams) <= spots_remaining:
            # All teams with this record go to relegation
            relegation_teams.extend(tied_teams)
        else:
            # Need tiebreaker - WINNER stays SAFE, LOSER goes to relegation
            # Use wildcard tiebreaker, but take from the END (losers)
            ordered = break_tie_wildcard(stats, tied_teams)
            # ordered is best-to-worst, so we take from the end for relegation
            losers = ordered[-(spots_remaining):]
            relegation_teams.extend(losers)
    
    # Now seed the relegation teams (worst = seed 1)
    # Group by record again and order
    rel_by_record = defaultdict(list)
    for team in relegation_teams:
        record = (stats[team]['wins'], stats[team]['losses'], stats[team]['ties'])
        rel_by_record[record].append(team)
    
    # Sort worst to best
    sorted_rel_records = sorted(rel_by_record.keys(), key=lambda r: (r[0], -r[1], -r[2]))
    
    seeded_relegation = []
    for record in sorted_rel_records:
        tied = rel_by_record[record]
        if len(tied) == 1:
            seeded_relegation.extend(tied)
        else:
            # For seeding within relegation, worst (tiebreaker loser) gets lower seed
            ordered = break_tie_wildcard(stats, tied)
            # Reverse so loser is first (worst seed)
            seeded_relegation.extend(reversed(ordered))
    
    # Return with seeds (1 = worst, most likely to be relegated)
    return [(i + 1, team) for i, team in enumerate(seeded_relegation)]


def simulate_week14_outcome(stats, outcome):
    """Simulate a Week 14 outcome and return updated stats."""
    new_stats = copy.deepcopy(stats)
    
    for matchup in WEEK14_MATCHUPS:
        away = matchup['away_team']
        home = matchup['home_team']
        is_div = matchup['is_division_game']
        
        result = outcome.get((away, home), 'home')
        
        if result == 'away':
            new_stats[away]['wins'] += 1
            new_stats[home]['losses'] += 1
            new_stats[away]['h2h'][home]['wins'] += 1
            new_stats[home]['h2h'][away]['losses'] += 1
            if is_div:
                new_stats[away]['division_wins'] += 1
                new_stats[home]['division_losses'] += 1
        elif result == 'home':
            new_stats[home]['wins'] += 1
            new_stats[away]['losses'] += 1
            new_stats[home]['h2h'][away]['wins'] += 1
            new_stats[away]['h2h'][home]['losses'] += 1
            if is_div:
                new_stats[home]['division_wins'] += 1
                new_stats[away]['division_losses'] += 1
    
    return new_stats


def generate_all_outcomes():
    """Generate all 64 possible Week 14 outcomes (no ties)."""
    matchups = [(m['away_team'], m['home_team']) for m in WEEK14_MATCHUPS]
    
    for results in product(['away', 'home'], repeat=6):
        outcome = {}
        for i, (away, home) in enumerate(matchups):
            outcome[(away, home)] = results[i]
        yield outcome


def analyze_all_scenarios():
    """Analyze all 64 Week 14 scenarios for both playoffs and relegation."""
    results = {
        'by_team': {team: {
            'championship_playoffs': 0,
            'bye': 0,
            'division_winner': 0,
            'relegation_playoffs': 0,
            'safe': 0,  # Not in either playoff
        } for team in TEAMS},
    }
    
    for outcome in generate_all_outcomes():
        new_stats = simulate_week14_outcome(STATS, outcome)
        playoff_teams = determine_playoff_teams(new_stats)
        relegation_teams = determine_relegation_teams(new_stats, playoff_teams)
        
        playoff_names = [team for _, team, _ in playoff_teams]
        relegation_names = [team for _, team in relegation_teams]
        
        for seed, team, is_div_winner in playoff_teams:
            results['by_team'][team]['championship_playoffs'] += 1
            if seed <= 2:
                results['by_team'][team]['bye'] += 1
            if is_div_winner:
                results['by_team'][team]['division_winner'] += 1
        
        for seed, team in relegation_teams:
            results['by_team'][team]['relegation_playoffs'] += 1
        
        for team in TEAMS:
            if team not in playoff_names and team not in relegation_names:
                results['by_team'][team]['safe'] += 1
    
    return results


def print_current_standings():
    """Print current standings after Week 13."""
    print("=" * 70)
    print("CURRENT STANDINGS (After Week 13)")
    print("=" * 70)
    
    for div in ['O', 'W', 'D']:
        print(f"\nDivision {div}:")
        ranking = rank_division(STATS, div)
        for i, team in enumerate(ranking):
            s = STATS[team]
            print(f"  {i+1}. {team:25} {s['wins']:2}-{s['losses']:<2} (Div: {s['division_wins']}-{s['division_losses']}) PF:{s['points_for']}")


def print_week14_matchups():
    """Print Week 14 matchups."""
    print("\n" + "=" * 70)
    print("WEEK 14 MATCHUPS")
    print("=" * 70)
    
    for m in WEEK14_MATCHUPS:
        away = m['away_team']
        home = m['home_team']
        div = "*" if m['is_division_game'] else ""
        print(f"  {away:25} at {home:25} {div}")


def print_playoff_picture(playoff_teams, relegation_teams, stats):
    """Print full playoff picture including relegation."""
    print("\n" + "-" * 50)
    print("🏆 CHAMPIONSHIP PLAYOFFS:")
    for seed, team, is_div_winner in playoff_teams:
        s = stats[team]
        dw = "DIV WINNER" if is_div_winner else "WILD CARD"
        bye = " (BYE)" if seed <= 2 else ""
        print(f"  #{seed}: {team:25} {s['wins']}-{s['losses']} {dw}{bye}")
    
    # Get safe teams
    playoff_names = [team for _, team, _ in playoff_teams]
    relegation_names = [team for _, team in relegation_teams]
    safe_teams = [t for t in TEAMS if t not in playoff_names and t not in relegation_names]
    
    if safe_teams:
        print("\n😌 SAFE (no playoffs):")
        for team in safe_teams:
            s = stats[team]
            print(f"     {team:25} {s['wins']}-{s['losses']}")
    
    print("\n⚠️  RELEGATION PLAYOFFS:")
    for seed, team in relegation_teams:
        s = stats[team]
        danger = "⬇️ " if seed == 1 else "  "
        print(f"  {danger}#{seed}: {team:25} {s['wins']}-{s['losses']}")


def analyze_margin_dependent_scenarios():
    """Analyze scenarios where the margin of victory matters."""
    print("\n" + "=" * 70)
    print("⚠️  MARGIN-DEPENDENT TIEBREAKERS")
    print("=" * 70)
    
    # Check ReBiggulators vs LPH (Division W)
    rb = 'The ReBiggulators'
    lph = 'Los Pollos Hermanos'
    
    print(f"\n📺 {rb} at {lph} (DIVISION W IMPLICATIONS)")
    print("-" * 60)
    
    rb_h2h_pts = STATS[rb]['h2h'][lph]['points_for']
    lph_h2h_pts = STATS[lph]['h2h'][rb]['points_for']
    
    print(f"  Current H2H points: LPH {lph_h2h_pts}, ReBiggulators {rb_h2h_pts}")
    print(f"  H2H point deficit for ReBiggulators: {lph_h2h_pts - rb_h2h_pts} points")
    
    print(f"\n  SCENARIO A: LPH wins")
    print(f"    → LPH: 10-4, ReBiggulators: 8-6")
    print(f"    → LPH wins Division W outright")
    
    print(f"\n  SCENARIO B: ReBiggulators wins by 1-2 points")
    print(f"    → Both 9-5, both 4-2 in division, H2H 1-1")
    print(f"    → Tiebreaker goes to H2H POINTS")
    print(f"    → LPH still has more H2H points → LPH wins Division W")
    
    print(f"\n  SCENARIO C: ReBiggulators wins by 3+ points")
    print(f"    → Both 9-5, both 4-2 in division, H2H 1-1")
    print(f"    → ReBiggulators has more H2H points → ReBiggulators wins Division W!")
    print(f"    → ReBiggulators gets #2 seed (BYE), LPH drops to #4 Wild Card")


def main():
    print_current_standings()
    print_week14_matchups()
    
    # Current playoff picture
    print("\n" + "=" * 70)
    print("CURRENT PLAYOFF PICTURE (if season ended now)")
    print("=" * 70)
    playoff_teams = determine_playoff_teams(STATS)
    relegation_teams = determine_relegation_teams(STATS, playoff_teams)
    print_playoff_picture(playoff_teams, relegation_teams, STATS)
    
    # Analyze margin-dependent scenarios
    analyze_margin_dependent_scenarios()
    
    # Analyze all scenarios
    print("\n" + "=" * 70)
    print("ANALYZING ALL 64 WEEK 14 SCENARIOS...")
    print("=" * 70)
    
    results = analyze_all_scenarios()
    
    # Summary tables
    print("\n" + "=" * 70)
    print("PLAYOFF & RELEGATION PROBABILITY BY TEAM")
    print("=" * 70)
    print(f"{'Team':<28} {'Champ':<12} {'Bye':<10} {'Safe':<10} {'Releg':<10}")
    print("-" * 70)
    
    # Sort by championship playoff probability, then by relegation (ascending)
    sorted_teams = sorted(
        TEAMS,
        key=lambda t: (
            -results['by_team'][t]['championship_playoffs'],
            results['by_team'][t]['relegation_playoffs']
        )
    )
    
    for team in sorted_teams:
        r = results['by_team'][team]
        champ_pct = r['championship_playoffs'] / 64 * 100
        bye_pct = r['bye'] / 64 * 100
        safe_pct = r['safe'] / 64 * 100
        releg_pct = r['relegation_playoffs'] / 64 * 100
        
        champ_str = f"{r['championship_playoffs']}/64" if r['championship_playoffs'] > 0 else "-"
        bye_str = f"{r['bye']}/64" if r['bye'] > 0 else "-"
        safe_str = f"{r['safe']}/64" if r['safe'] > 0 else "-"
        releg_str = f"{r['relegation_playoffs']}/64" if r['relegation_playoffs'] > 0 else "-"
        
        # Add visual indicators
        if r['championship_playoffs'] == 64:
            status = "✅"
        elif r['relegation_playoffs'] == 64:
            status = "⚠️ "
        elif r['safe'] == 64:
            status = "😌"
        else:
            status = "  "
        
        print(f"{status}{team:<26} {champ_str:<12} {bye_str:<10} {safe_str:<10} {releg_str:<10}")
    
    # Key games summary
    print("\n" + "=" * 70)
    print("KEY GAMES SUMMARY")
    print("=" * 70)
    
    print("\n🏆 CHAMPIONSHIP PLAYOFF IMPLICATIONS:")
    
    print("\n🔥 The ReBiggulators at Los Pollos Hermanos")
    print("   • LPH win → LPH Division W champ (#2 bye)")
    print("   • ReBiggulators win by 1-2 pts → LPH Division W champ (#2 bye)")
    print("   • ReBiggulators win by 3+ pts → ReBiggulators Division W champ (#2 bye)!")
    
    print("\n🔥 The Original Series at Free The Nip")
    print("   • TOS win → TOS Division D champ (#3), FTN #6 WC")
    print("   • FTN win → FTN Division D champ (#3), TOS #6 WC")
    
    print("\n⚠️  RELEGATION PLAYOFF IMPLICATIONS:")
    
    print("\n🔥 Gashouse Gorillas at Ytterby Yetis")
    print("   • Winner improves to 7-7 (likely SAFE)")
    print("   • Loser drops to 5-9 or 6-8 (relegation danger)")
    
    print("\n🔥 Hampden Has-Beens at One Direction Two")  
    print("   • Hampden win → 6-8, may escape relegation")
    print("   • One Direction win → 5-9, but One Direction likely in anyway")
    
    print("\n🔥 Lester Pearls at East Shore Boys")
    print("   • Lester win → 6-8, may escape relegation")
    print("   • East Shore win → 5-9, but East Shore likely in anyway")
    
    print("\n😴 No playoff/relegation implications:")
    print("   • Boomie's Boys at Mobius Strippers (both locked for championship)")
    
    # Detailed relegation analysis
    print("\n" + "=" * 70)
    print("RELEGATION SCENARIOS DETAIL")
    print("=" * 70)
    
    print("\n📊 Possible final records for bubble teams:")
    bubble_teams = ['Gashouse Gorillas', 'Hampden Has-Beens', 'Lester Pearls', 'Ytterby Yetis']
    
    for team in bubble_teams:
        s = STATS[team]
        # Find their Week 14 matchup
        for m in WEEK14_MATCHUPS:
            if m['away_team'] == team or m['home_team'] == team:
                opp = m['home_team'] if m['away_team'] == team else m['away_team']
                print(f"\n  {team} ({s['wins']}-{s['losses']}) vs {opp}:")
                print(f"    Win → {s['wins']+1}-{s['losses']} | Lose → {s['wins']}-{s['losses']+1}")
                break
    
    print("\n📋 Who gets relegated in each scenario:")
    print("   (Teams sorted worst to best within each record tier)")
    print("\n   Current relegation order (if season ended now):")
    playoff_teams = determine_playoff_teams(STATS)
    relegation_teams = determine_relegation_teams(STATS, playoff_teams)
    for seed, team in relegation_teams:
        s = STATS[team]
        print(f"     #{seed}: {team} ({s['wins']}-{s['losses']})")
    
    # Save results
    with open('playoff_scenarios.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n✅ Results saved to playoff_scenarios.json")


if __name__ == "__main__":
    main()
