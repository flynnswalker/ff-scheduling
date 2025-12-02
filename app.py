#!/usr/bin/env python3
"""
Fantasy Football Playoff Scenario Analyzer - Web Application
Supports multiple leagues: WFFL, DFFL, FFPL
"""

from flask import Flask, render_template, jsonify, request
import json
import copy
from collections import defaultdict

app = Flask(__name__)

# Load all leagues data
with open('all_leagues_data.json') as f:
    ALL_LEAGUES = json.load(f)


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


def get_h2h_record(stats, team1, team2):
    h2h = stats[team1]['h2h'].get(team2, {'wins': 0, 'losses': 0, 'ties': 0})
    return h2h['wins'], h2h['losses'], h2h['ties']


def get_h2h_record_vs_group(stats, team, opponents):
    wins = losses = ties = 0
    for opp in opponents:
        if opp != team:
            h2h = stats[team]['h2h'].get(opp, {'wins': 0, 'losses': 0, 'ties': 0})
            wins += h2h['wins']
            losses += h2h['losses']
            ties += h2h['ties']
    return wins, losses, ties


def calculate_strength_of_schedule(stats, team, teams):
    total_opp_wins = 0
    total_opp_losses = 0
    total_opp_ties = 0
    
    for opp in teams:
        if opp != team:
            h2h = stats[team]['h2h'].get(opp, {'wins': 0, 'losses': 0, 'ties': 0})
            games_vs_opp = h2h['wins'] + h2h['losses'] + h2h['ties']
            
            if games_vs_opp > 0:
                opp_stats = stats[opp]
                total_opp_wins += opp_stats['wins'] * games_vs_opp
                total_opp_losses += opp_stats['losses'] * games_vs_opp
                total_opp_ties += opp_stats['ties'] * games_vs_opp
    
    return calculate_win_pct(total_opp_wins, total_opp_losses, total_opp_ties)


def break_tie_division(stats, tied_teams, divisions, h2h_points_override=None):
    if len(tied_teams) == 1:
        return tied_teams
    if len(tied_teams) == 2:
        return _break_tie_division_two(stats, tied_teams, h2h_points_override)
    return _break_tie_division_multi(stats, tied_teams, divisions, h2h_points_override)


def _break_tie_division_two(stats, tied_teams, h2h_points_override=None):
    t1, t2 = tied_teams
    
    w1, l1, _ = get_h2h_record(stats, t1, t2)
    w2, l2, _ = get_h2h_record(stats, t2, t1)
    
    if w1 > w2:
        return [t1, t2]
    elif w2 > w1:
        return [t2, t1]
    
    div1_pct = calculate_win_pct(stats[t1]['division_wins'], stats[t1]['division_losses'], stats[t1]['division_ties'])
    div2_pct = calculate_win_pct(stats[t2]['division_wins'], stats[t2]['division_losses'], stats[t2]['division_ties'])
    
    if div1_pct > div2_pct:
        return [t1, t2]
    elif div2_pct > div1_pct:
        return [t2, t1]
    
    if h2h_points_override and (t1, t2) in h2h_points_override:
        h2h_pts1, h2h_pts2 = h2h_points_override[(t1, t2)]
    else:
        h2h_pts1 = stats[t1]['h2h'].get(t2, {}).get('points_for', 0)
        h2h_pts2 = stats[t2]['h2h'].get(t1, {}).get('points_for', 0)
    
    if h2h_pts1 > h2h_pts2:
        return [t1, t2]
    elif h2h_pts2 > h2h_pts1:
        return [t2, t1]
    
    if stats[t1]['points_for'] > stats[t2]['points_for']:
        return [t1, t2]
    elif stats[t2]['points_for'] > stats[t1]['points_for']:
        return [t2, t1]
    
    if stats[t1]['matrix_rank'] < stats[t2]['matrix_rank']:
        return [t1, t2]
    elif stats[t2]['matrix_rank'] < stats[t1]['matrix_rank']:
        return [t2, t1]
    
    return sorted([t1, t2])


def _break_tie_division_multi(stats, tied_teams, divisions, h2h_points_override=None):
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
                ordered_best = _break_tie_division_multi(stats, best_teams, divisions, h2h_points_override)
                result.extend(ordered_best)
                for t in ordered_best:
                    remaining.remove(t)
            continue
        
        div_records = {t: calculate_win_pct(stats[t]['division_wins'], stats[t]['division_losses'], stats[t]['division_ties']) for t in remaining}
        best_div = max(div_records.values())
        best_teams = [t for t in remaining if div_records[t] == best_div]
        
        if len(best_teams) < len(remaining):
            if len(best_teams) == 1:
                result.append(best_teams[0])
                remaining.remove(best_teams[0])
            else:
                ordered_best = _break_tie_division_multi(stats, best_teams, divisions, h2h_points_override)
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
                ordered_best = _break_tie_division_multi(stats, best_teams, divisions, h2h_points_override)
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


def break_tie_wildcard(stats, tied_teams, teams, divisions):
    if len(tied_teams) == 1:
        return tied_teams
    
    by_division = defaultdict(list)
    for team in tied_teams:
        div = get_team_division(team, divisions)
        by_division[div].append(team)
    
    if len(by_division) == 1:
        return break_tie_division(stats, tied_teams, divisions)
    
    ordered_by_div = {}
    for div, div_teams in by_division.items():
        if len(div_teams) > 1:
            ordered_by_div[div] = break_tie_division(stats, div_teams, divisions)
        else:
            ordered_by_div[div] = div_teams
    
    result = []
    remaining_by_div = {div: list(div_teams) for div, div_teams in ordered_by_div.items()}
    
    while sum(len(teams) for teams in remaining_by_div.values()) > 0:
        candidates = []
        for div, div_teams in remaining_by_div.items():
            if div_teams:
                candidates.append(div_teams[0])
        
        if len(candidates) == 1:
            team = candidates[0]
            result.append(team)
            div = get_team_division(team, divisions)
            remaining_by_div[div].pop(0)
        else:
            best = _compare_cross_division(stats, candidates, teams, divisions)
            result.append(best)
            div = get_team_division(best, divisions)
            remaining_by_div[div].pop(0)
    
    return result


def _compare_cross_division(stats, candidates, all_teams, divisions):
    if len(candidates) == 1:
        return candidates[0]
    
    if len(candidates) == 2:
        t1, t2 = candidates
        w1, l1, _ = get_h2h_record(stats, t1, t2)
        w2, l2, _ = get_h2h_record(stats, t2, t1)
        if w1 > w2:
            return t1
        elif w2 > w1:
            return t2
        
        sos1 = calculate_strength_of_schedule(stats, t1, all_teams)
        sos2 = calculate_strength_of_schedule(stats, t2, all_teams)
        if sos1 > sos2:
            return t1
        elif sos2 > sos1:
            return t2
        
        if stats[t1]['points_for'] > stats[t2]['points_for']:
            return t1
        elif stats[t2]['points_for'] > stats[t1]['points_for']:
            return t2
        
        if stats[t1]['matrix_rank'] < stats[t2]['matrix_rank']:
            return t1
        elif stats[t2]['matrix_rank'] < stats[t1]['matrix_rank']:
            return t2
        
        return sorted(candidates)[0]
    
    remaining = list(candidates)
    
    h2h_records = {}
    for team in remaining:
        w, l, t = get_h2h_record_vs_group(stats, team, remaining)
        h2h_records[team] = calculate_win_pct(w, l, t)
    
    best_pct = max(h2h_records.values())
    best_teams = [t for t in remaining if h2h_records[t] == best_pct]
    
    if len(best_teams) == 1:
        return best_teams[0]
    
    remaining = best_teams
    
    sos = {t: calculate_strength_of_schedule(stats, t, all_teams) for t in remaining}
    best_sos = max(sos.values())
    best_teams = [t for t in remaining if sos[t] == best_sos]
    
    if len(best_teams) == 1:
        return best_teams[0]
    
    remaining = best_teams
    
    points = {t: stats[t]['points_for'] for t in remaining}
    best_pts = max(points.values())
    best_teams = [t for t in remaining if points[t] == best_pts]
    
    if len(best_teams) == 1:
        return best_teams[0]
    
    remaining = best_teams
    
    ranks = {t: stats[t]['matrix_rank'] for t in remaining}
    best_rank = min(ranks.values())
    best_teams = [t for t in remaining if ranks[t] == best_rank]
    
    if len(best_teams) == 1:
        return best_teams[0]
    
    return sorted(remaining)[0]


def rank_division(stats, division_teams, divisions, h2h_points_override=None):
    by_record = defaultdict(list)
    for team in division_teams:
        record = (stats[team]['wins'], stats[team]['losses'], stats[team]['ties'])
        by_record[record].append(team)
    
    sorted_records = sorted(by_record.keys(), key=lambda r: (-r[0], r[1], r[2]))
    
    ranking = []
    for record in sorted_records:
        tied_teams = by_record[record]
        if len(tied_teams) == 1:
            ranking.extend(tied_teams)
        else:
            ranking.extend(break_tie_division(stats, tied_teams, divisions, h2h_points_override))
    
    return ranking


def determine_playoff_teams(stats, teams, divisions, h2h_points_override=None):
    division_rankings = {}
    for div, div_teams in divisions.items():
        division_rankings[div] = rank_division(stats, div_teams, divisions, h2h_points_override)
    
    division_winners = [division_rankings[div][0] for div in sorted(divisions.keys())]
    non_winners = [t for t in teams if t not in division_winners]
    
    by_record = defaultdict(list)
    for team in non_winners:
        record = (stats[team]['wins'], stats[team]['losses'], stats[team]['ties'])
        by_record[record].append(team)
    
    sorted_records = sorted(by_record.keys(), key=lambda r: (-r[0], r[1], r[2]))
    
    num_wildcards = 6 - len(division_winners)
    wild_cards = []
    for record in sorted_records:
        if len(wild_cards) >= num_wildcards:
            break
        tied_teams = by_record[record]
        spots_remaining = num_wildcards - len(wild_cards)
        if len(tied_teams) <= spots_remaining:
            wild_cards.extend(tied_teams)
        else:
            ordered = break_tie_wildcard(stats, tied_teams, teams, divisions)
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
            seeded_winners.extend(break_tie_wildcard(stats, tied, teams, divisions))
    
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
            seeded_wildcards.extend(break_tie_wildcard(stats, tied, teams, divisions))
    
    playoff_teams = []
    for i, team in enumerate(seeded_winners):
        playoff_teams.append({
            'seed': i + 1,
            'team': team,
            'is_division_winner': True,
            'has_bye': i < 2,
            'record': f"{stats[team]['wins']}-{stats[team]['losses']}",
            'division': get_team_division(team, divisions)
        })
    for i, team in enumerate(seeded_wildcards):
        playoff_teams.append({
            'seed': len(seeded_winners) + i + 1,
            'team': team,
            'is_division_winner': False,
            'has_bye': False,
            'record': f"{stats[team]['wins']}-{stats[team]['losses']}",
            'division': get_team_division(team, divisions)
        })
    
    return playoff_teams


def determine_relegation_teams(stats, playoff_teams, teams, divisions):
    playoff_team_names = [p['team'] for p in playoff_teams]
    non_playoff_teams = [t for t in teams if t not in playoff_team_names]
    
    by_record = defaultdict(list)
    for team in non_playoff_teams:
        record = (stats[team]['wins'], stats[team]['losses'], stats[team]['ties'])
        by_record[record].append(team)
    
    sorted_records = sorted(by_record.keys(), key=lambda r: (r[0], -r[1], -r[2]))
    
    relegation_teams = []
    for record in sorted_records:
        if len(relegation_teams) >= 4:
            break
        tied_teams = by_record[record]
        spots_remaining = 4 - len(relegation_teams)
        if len(tied_teams) <= spots_remaining:
            relegation_teams.extend(tied_teams)
        else:
            ordered = break_tie_wildcard(stats, tied_teams, teams, divisions)
            losers = ordered[-(spots_remaining):]
            relegation_teams.extend(losers)
    
    rel_by_record = defaultdict(list)
    for team in relegation_teams:
        record = (stats[team]['wins'], stats[team]['losses'], stats[team]['ties'])
        rel_by_record[record].append(team)
    
    sorted_rel_records = sorted(rel_by_record.keys(), key=lambda r: (r[0], -r[1], -r[2]))
    
    seeded_relegation = []
    for record in sorted_rel_records:
        tied = rel_by_record[record]
        if len(tied) == 1:
            seeded_relegation.extend(tied)
        else:
            ordered = break_tie_wildcard(stats, tied, teams, divisions)
            seeded_relegation.extend(reversed(ordered))
    
    result = []
    for i, team in enumerate(seeded_relegation):
        result.append({
            'seed': i + 1,
            'team': team,
            'record': f"{stats[team]['wins']}-{stats[team]['losses']}",
            'division': get_team_division(team, divisions)
        })
    
    return result


def simulate_week14_outcome(base_stats, selections, matchups, divisions, league_name):
    """Simulate Week 14 based on user selections."""
    new_stats = copy.deepcopy(base_stats)
    h2h_points_override = None
    
    for matchup in matchups:
        away = matchup['away_team']
        home = matchup['home_team']
        is_div = matchup['is_division_game']
        game_id = f"{away}_at_{home}".replace("'", "").replace(" ", "_")
        
        selection = selections.get(game_id, {'winner': 'home', 'margin': 5})
        winner_side = selection.get('winner', 'home')
        margin = selection.get('margin', 5)
        
        if winner_side == 'away':
            new_stats[away]['wins'] += 1
            new_stats[home]['losses'] += 1
            if away in new_stats[away]['h2h']:
                pass  # Already handled
            new_stats[away]['h2h'][home]['wins'] = new_stats[away]['h2h'].get(home, {}).get('wins', 0) + 1
            new_stats[home]['h2h'][away]['losses'] = new_stats[home]['h2h'].get(away, {}).get('losses', 0) + 1
            if is_div:
                new_stats[away]['division_wins'] += 1
                new_stats[home]['division_losses'] += 1
        else:
            new_stats[home]['wins'] += 1
            new_stats[away]['losses'] += 1
            new_stats[home]['h2h'][away]['wins'] = new_stats[home]['h2h'].get(away, {}).get('wins', 0) + 1
            new_stats[away]['h2h'][home]['losses'] = new_stats[away]['h2h'].get(home, {}).get('losses', 0) + 1
            if is_div:
                new_stats[home]['division_wins'] += 1
                new_stats[away]['division_losses'] += 1
        
        # Handle margin for FFPL LPH vs ReBiggulators
        if league_name == 'FFPL' and away == 'The ReBiggulators' and home == 'Los Pollos Hermanos':
            if winner_side == 'away' and margin >= 3:
                h2h_points_override = {
                    ('The ReBiggulators', 'Los Pollos Hermanos'): (61, 53),
                    ('Los Pollos Hermanos', 'The ReBiggulators'): (53, 61),
                }
    
    return new_stats, h2h_points_override


def get_matchup_win_probability(away_team, home_team, matchup_probs):
    """Get win probability for away team based on Power Matrix."""
    key = f"{away_team}__at__{home_team}"
    if key in matchup_probs:
        return matchup_probs[key]['away_win_pct']
    return 0.5


def get_team_summary_weighted(league_name):
    """Get summary of each team's playoff/relegation situation."""
    league_data = ALL_LEAGUES[league_name]
    teams = league_data['teams']
    divisions = league_data['divisions']
    stats = league_data['stats']
    matchups = league_data['week14_matchups']
    matchup_probs = league_data.get('matchup_probs', {})
    has_relegation = league_data['has_relegation']
    
    summary = {team: {
        'current_record': f"{stats[team]['wins']}-{stats[team]['losses']}",
        'division': get_team_division(team, divisions),
        'championship_pct': 0.0,
        'bye_pct': 0.0,
        'relegation_pct': 0.0,
        'safe_pct': 0.0,
        'status': '',
    } for team in teams}
    
    matchup_list = [(m['away_team'], m['home_team']) for m in matchups]
    
    game_probs = []
    for away, home in matchup_list:
        away_prob = get_matchup_win_probability(away, home, matchup_probs)
        game_probs.append((away_prob, 1 - away_prob))
    
    from itertools import product
    
    total_prob = 0.0
    num_games = len(matchup_list)
    
    if num_games == 0:
        # No games to simulate
        playoff_teams = determine_playoff_teams(stats, teams, divisions)
        playoff_names = [p['team'] for p in playoff_teams]
        
        for p in playoff_teams:
            summary[p['team']]['championship_pct'] = 100.0
            if p['has_bye']:
                summary[p['team']]['bye_pct'] = 100.0
        
        if has_relegation:
            relegation_teams = determine_relegation_teams(stats, playoff_teams, teams, divisions)
            relegation_names = [r['team'] for r in relegation_teams]
            for r in relegation_teams:
                summary[r['team']]['relegation_pct'] = 100.0
        else:
            relegation_names = []
        
        for team in teams:
            if team not in playoff_names and team not in relegation_names:
                summary[team]['safe_pct'] = 100.0
    else:
        for results in product([0, 1], repeat=num_games):
            scenario_prob = 1.0
            for i, result in enumerate(results):
                scenario_prob *= game_probs[i][result]
            
            total_prob += scenario_prob
            
            selections = {}
            for i, (away, home) in enumerate(matchup_list):
                game_id = f"{away}_at_{home}".replace("'", "").replace(" ", "_")
                winner = 'away' if results[i] == 0 else 'home'
                selections[game_id] = {'winner': winner, 'margin': 5}
            
            new_stats, h2h_override = simulate_week14_outcome(stats, selections, matchups, divisions, league_name)
            playoff_teams = determine_playoff_teams(new_stats, teams, divisions, h2h_override)
            
            playoff_names = [p['team'] for p in playoff_teams]
            
            if has_relegation:
                relegation_teams = determine_relegation_teams(new_stats, playoff_teams, teams, divisions)
                relegation_names = [r['team'] for r in relegation_teams]
            else:
                relegation_names = []
            
            for p in playoff_teams:
                summary[p['team']]['championship_pct'] += scenario_prob
                if p['has_bye']:
                    summary[p['team']]['bye_pct'] += scenario_prob
            
            for r in relegation_names:
                summary[r]['relegation_pct'] += scenario_prob
            
            for team in teams:
                if team not in playoff_names and team not in relegation_names:
                    summary[team]['safe_pct'] += scenario_prob
        
        # Convert to percentages
        for team in teams:
            if total_prob > 0:
                summary[team]['championship_pct'] = round(summary[team]['championship_pct'] / total_prob * 100, 1)
                summary[team]['bye_pct'] = round(summary[team]['bye_pct'] / total_prob * 100, 1)
                summary[team]['relegation_pct'] = round(summary[team]['relegation_pct'] / total_prob * 100, 1)
                summary[team]['safe_pct'] = round(summary[team]['safe_pct'] / total_prob * 100, 1)
    
    # Set status
    for team in teams:
        if summary[team]['championship_pct'] >= 99.9:
            summary[team]['status'] = 'clinched_playoffs'
        elif summary[team]['relegation_pct'] >= 99.9:
            summary[team]['status'] = 'clinched_relegation'
        elif summary[team]['safe_pct'] >= 99.9:
            summary[team]['status'] = 'safe'
        elif summary[team]['championship_pct'] > 0:
            summary[team]['status'] = 'playoff_contender'
        elif summary[team]['relegation_pct'] > 0:
            summary[team]['status'] = 'relegation_danger'
        else:
            summary[team]['status'] = 'safe'
    
    return summary


@app.route('/')
def index():
    leagues_data = {}
    
    for league_name, league_info in ALL_LEAGUES.items():
        stats = league_info['stats']
        divisions = league_info['divisions']
        matchup_probs = league_info.get('matchup_probs', {})
        
        matchups = []
        for m in league_info['week14_matchups']:
            away = m['away_team']
            home = m['home_team']
            game_id = f"{away}_at_{home}".replace("'", "").replace(" ", "_")
            
            away_win_pct = get_matchup_win_probability(away, home, matchup_probs)
            home_win_pct = 1 - away_win_pct
            
            favored = 'away' if away_win_pct > home_win_pct else 'home'
            
            has_margin_impact = (league_name == 'FFPL' and away == 'The ReBiggulators' and home == 'Los Pollos Hermanos')
            margin_note = "Margin affects division title (ReBigs need 3+ to win Div W)" if has_margin_impact else ""
            
            matchups.append({
                'game_id': game_id,
                'away_team': away,
                'away_record': f"{stats[away]['wins']}-{stats[away]['losses']}",
                'away_win_pct': round(away_win_pct * 100, 1),
                'home_team': home,
                'home_record': f"{stats[home]['wins']}-{stats[home]['losses']}",
                'home_win_pct': round(home_win_pct * 100, 1),
                'is_division_game': m['is_division_game'],
                'has_margin_impact': has_margin_impact,
                'margin_note': margin_note,
                'favored': favored,
            })
        
        leagues_data[league_name] = {
            'matchups': matchups,
            'has_relegation': league_info['has_relegation'],
            'league_id': league_info['league_id'],
        }
    
    return render_template('index.html', leagues=leagues_data)


@app.route('/api/scenario/<league_name>', methods=['POST'])
def calculate_scenario(league_name):
    """Calculate playoff picture based on selected outcomes."""
    if league_name not in ALL_LEAGUES:
        return jsonify({'error': 'Unknown league'}), 404
    
    league_data = ALL_LEAGUES[league_name]
    selections = request.json.get('selections', {})
    
    stats = league_data['stats']
    teams = league_data['teams']
    divisions = league_data['divisions']
    matchups = league_data['week14_matchups']
    has_relegation = league_data['has_relegation']
    
    new_stats, h2h_override = simulate_week14_outcome(stats, selections, matchups, divisions, league_name)
    playoff_teams = determine_playoff_teams(new_stats, teams, divisions, h2h_override)
    
    if has_relegation:
        relegation_teams = determine_relegation_teams(new_stats, playoff_teams, teams, divisions)
    else:
        relegation_teams = []
    
    playoff_names = [p['team'] for p in playoff_teams]
    relegation_names = [r['team'] for r in relegation_teams]
    safe_teams = []
    for team in teams:
        if team not in playoff_names and team not in relegation_names:
            safe_teams.append({
                'team': team,
                'record': f"{new_stats[team]['wins']}-{new_stats[team]['losses']}",
                'division': get_team_division(team, divisions)
            })
    
    return jsonify({
        'playoff_teams': playoff_teams,
        'relegation_teams': relegation_teams,
        'safe_teams': safe_teams,
        'has_relegation': has_relegation,
    })


@app.route('/api/summary/<league_name>')
def team_summary(league_name):
    """Get summary of playoff situations for all teams in a league."""
    if league_name not in ALL_LEAGUES:
        return jsonify({'error': 'Unknown league'}), 404
    
    summary = get_team_summary_weighted(league_name)
    teams = ALL_LEAGUES[league_name]['teams']
    has_relegation = ALL_LEAGUES[league_name]['has_relegation']
    
    sorted_teams = sorted(
        teams,
        key=lambda t: (-summary[t]['championship_pct'], summary[t]['relegation_pct'])
    )
    
    result = [{**summary[team], 'team': team} for team in sorted_teams]
    return jsonify({
        'teams': result,
        'has_relegation': has_relegation,
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
