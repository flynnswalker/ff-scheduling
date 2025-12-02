#!/usr/bin/env python3
"""
Get full game history for tiebreaker calculations.
Need H2H records, division records, and points scored.
"""

import requests
from bs4 import BeautifulSoup
import re
import json

BASE_URL = "https://www.dougin.com/ffl"
LEAGUE_ID = 3

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

# All team names
ALL_TEAMS = [
    "Boomie's Boys",
    "Mobius Strippers",
    "Los Pollos Hermanos",
    "The ReBiggulators",
    "The Original Series",
    "Hampden Has-Beens",
    "Free The Nip",
    "One Direction Two",
    "Lester Pearls",
    "Gashouse Gorillas",
    "East Shore Boys",
    "Ytterby Yetis",
]

# Divisions
DIVISIONS = {
    'O': ["Boomie's Boys", "Mobius Strippers", "Hampden Has-Beens", "One Direction Two"],
    'W': ["Los Pollos Hermanos", "The ReBiggulators", "Gashouse Gorillas", "Ytterby Yetis"],
    'D': ["The Original Series", "Free The Nip", "Lester Pearls", "East Shore Boys"],
}

def get_team_division(team):
    """Get the division for a team."""
    for div, teams in DIVISIONS.items():
        if team in teams:
            return div
    return None

def normalize_team_name(name):
    """Normalize team name."""
    name = name.strip().replace('`', "'")
    
    # Partial matches
    name_lower = name.lower()
    if 'boomie' in name_lower:
        return "Boomie's Boys"
    if 'mobius' in name_lower:
        return "Mobius Strippers"
    if 'pollos' in name_lower:
        return "Los Pollos Hermanos"
    if 'rebiggulator' in name_lower:
        return "The ReBiggulators"
    if 'original' in name_lower:
        return "The Original Series"
    if 'hampden' in name_lower:
        return "Hampden Has-Beens"
    if 'nip' in name_lower:
        return "Free The Nip"
    if 'direction' in name_lower:
        return "One Direction Two"
    if 'lester' in name_lower or 'pearl' in name_lower:
        return "Lester Pearls"
    if 'gashouse' in name_lower or 'gorilla' in name_lower:
        return "Gashouse Gorillas"
    if 'east shore' in name_lower or 'shore boy' in name_lower:
        return "East Shore Boys"
    if 'ytterby' in name_lower or 'yeti' in name_lower:
        return "Ytterby Yetis"
    
    return name

def parse_schedule():
    """Parse all games from the schedule."""
    session = requests.Session()
    session.headers.update(HEADERS)
    
    url = f"{BASE_URL}/FFL.cfm?FID=LeagueSchedule.cfm&League={LEAGUE_ID}"
    resp = session.get(url, timeout=10)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    all_games = []
    week14_matchups = []
    
    # Find all game links with scores - they contain the game info
    game_links = soup.find_all('a', class_='base_link2')
    
    for link in game_links:
        game_text = link.get_text(strip=True)
        
        # Pattern for played games: "Team1 (score1) at Team2 (score2)"
        played_match = re.match(r'(.+?)\s*\((\d+)\)\s*at\s*(.+?)\s*\((\d+)\)', game_text)
        
        if played_match:
            away_team = normalize_team_name(played_match.group(1))
            away_score = int(played_match.group(2))
            home_team = normalize_team_name(played_match.group(3))
            home_score = int(played_match.group(4))
            
            if away_team in ALL_TEAMS and home_team in ALL_TEAMS:
                game = {
                    'away_team': away_team,
                    'away_score': away_score,
                    'home_team': home_team,
                    'home_score': home_score,
                    'played': True,
                }
                
                # Determine winner
                if away_score > home_score:
                    game['winner'] = away_team
                    game['loser'] = home_team
                elif home_score > away_score:
                    game['winner'] = home_team
                    game['loser'] = away_team
                else:
                    game['winner'] = None  # Tie
                    game['loser'] = None
                
                # Is this a division game?
                away_div = get_team_division(away_team)
                home_div = get_team_division(home_team)
                game['is_division_game'] = (away_div == home_div)
                
                all_games.append(game)
    
    # Assign weeks - games are listed in order, 6 per week
    for i, game in enumerate(all_games):
        game['week'] = (i // 6) + 1
    
    # Now parse Week 14 matchups (unplayed games)
    # They're in the schedule text without scores
    text = soup.get_text()
    text_clean = re.sub(r'\s+', ' ', text)
    
    # Find Week 14 section
    week14_match = re.search(r'Week 14\s*(.*?)(?:Playoffs?|Championship|I\'m a dialog|$)', text_clean, re.IGNORECASE)
    
    if week14_match:
        week14_text = week14_match.group(1)
        
        # Parse unplayed games: "Team1 at Team2 Team3 at Team4..."
        # Split on " at " and pair teams
        parts = re.split(r'\s+at\s+', week14_text)
        
        for i in range(len(parts) - 1):
            away_raw = parts[i].strip()
            home_raw = parts[i + 1].strip()
            
            # Find the last team name in away_raw
            away_team = None
            for team in ALL_TEAMS:
                team_pattern = team.replace("'", "[`']")
                if re.search(rf'{team_pattern}$', away_raw, re.IGNORECASE):
                    away_team = team
                    break
            
            # Find the first team name in home_raw
            home_team = None
            for team in ALL_TEAMS:
                team_pattern = team.replace("'", "[`']")
                if re.search(rf'^{team_pattern}', home_raw, re.IGNORECASE):
                    home_team = team
                    break
            
            if away_team and home_team:
                matchup = {
                    'week': 14,
                    'away_team': away_team,
                    'away_score': None,
                    'home_team': home_team,
                    'home_score': None,
                    'played': False,
                    'winner': None,
                    'loser': None,
                    'is_division_game': get_team_division(away_team) == get_team_division(home_team),
                }
                week14_matchups.append(matchup)
    
    return all_games, week14_matchups

def calculate_team_stats(games):
    """Calculate all stats needed for tiebreakers."""
    
    # Only use played games
    played_games = [g for g in games if g['played']]
    
    # Initialize stats for each team
    stats = {}
    for team in ALL_TEAMS:
        stats[team] = {
            'team': team,
            'division': get_team_division(team),
            'wins': 0,
            'losses': 0,
            'ties': 0,
            'points_for': 0,
            'points_against': 0,
            'division_wins': 0,
            'division_losses': 0,
            'division_ties': 0,
            'h2h': {},  # Head-to-head vs each opponent
            'games_played': [],
        }
        # Initialize H2H against each other team
        for opp in ALL_TEAMS:
            if opp != team:
                stats[team]['h2h'][opp] = {
                    'wins': 0,
                    'losses': 0,
                    'ties': 0,
                    'points_for': 0,
                    'points_against': 0,
                }
    
    # Process each played game
    for game in played_games:
        away = game['away_team']
        home = game['home_team']
        away_score = game['away_score']
        home_score = game['home_score']
        is_div = game['is_division_game']
        
        # Track games
        stats[away]['games_played'].append(game)
        stats[home]['games_played'].append(game)
        
        # Update points
        stats[away]['points_for'] += away_score
        stats[away]['points_against'] += home_score
        stats[home]['points_for'] += home_score
        stats[home]['points_against'] += away_score
        
        # Update H2H points
        stats[away]['h2h'][home]['points_for'] += away_score
        stats[away]['h2h'][home]['points_against'] += home_score
        stats[home]['h2h'][away]['points_for'] += home_score
        stats[home]['h2h'][away]['points_against'] += away_score
        
        # Update W/L
        if away_score > home_score:
            stats[away]['wins'] += 1
            stats[home]['losses'] += 1
            stats[away]['h2h'][home]['wins'] += 1
            stats[home]['h2h'][away]['losses'] += 1
            if is_div:
                stats[away]['division_wins'] += 1
                stats[home]['division_losses'] += 1
        elif home_score > away_score:
            stats[home]['wins'] += 1
            stats[away]['losses'] += 1
            stats[home]['h2h'][away]['wins'] += 1
            stats[away]['h2h'][home]['losses'] += 1
            if is_div:
                stats[home]['division_wins'] += 1
                stats[away]['division_losses'] += 1
        else:
            stats[away]['ties'] += 1
            stats[home]['ties'] += 1
            stats[away]['h2h'][home]['ties'] += 1
            stats[home]['h2h'][away]['ties'] += 1
            if is_div:
                stats[away]['division_ties'] += 1
                stats[home]['division_ties'] += 1
    
    return stats

def get_matrix_rank(session=None):
    """Get matrix rank for each team from Power Matrix page."""
    if session is None:
        session = requests.Session()
        session.headers.update(HEADERS)
    
    url = f"{BASE_URL}/FFL.cfm?Matrix=1&League={LEAGUE_ID}"
    resp = session.get(url, timeout=10)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    matrix_ranks = {}
    
    tables = soup.find_all('table')
    for table in tables:
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all(['th', 'td'])
            cell_texts = [c.get_text(strip=True) for c in cells]
            
            if len(cell_texts) >= 3:
                first = cell_texts[0]
                if re.match(r'^\d+\.$', first):
                    rank = int(first.replace('.', ''))
                    team = normalize_team_name(cell_texts[2])
                    if team in ALL_TEAMS and team not in matrix_ranks:
                        matrix_ranks[team] = rank
    
    return matrix_ranks

def main():
    print("=" * 60)
    print("Extracting Full Game History for Tiebreakers")
    print("=" * 60)
    
    played_games, week14_matchups = parse_schedule()
    
    print(f"\nPlayed games (Weeks 1-13): {len(played_games)}")
    print(f"Week 14 matchups: {len(week14_matchups)}")
    
    # Show games by week
    for week in range(1, 14):
        week_games = [g for g in played_games if g.get('week') == week]
        if week_games:
            print(f"\nWeek {week}: {len(week_games)} games")
            for g in week_games:
                div_marker = "*" if g['is_division_game'] else ""
                print(f"  {g['away_team']:25} ({g['away_score']:2}) at {g['home_team']:25} ({g['home_score']:2}) {div_marker}")
    
    # Show Week 14
    print(f"\nWeek 14 (upcoming): {len(week14_matchups)} games")
    for g in week14_matchups:
        div_marker = "*" if g['is_division_game'] else ""
        print(f"  {g['away_team']:25}      at {g['home_team']:25}      {div_marker}")
    
    # Calculate stats
    stats = calculate_team_stats(played_games)
    
    # Get matrix ranks
    session = requests.Session()
    session.headers.update(HEADERS)
    matrix_ranks = get_matrix_rank(session)
    
    # Add matrix rank to stats
    for team in stats:
        stats[team]['matrix_rank'] = matrix_ranks.get(team, 99)
    
    print("\n" + "=" * 60)
    print("Team Statistics (After Week 13)")
    print("=" * 60)
    
    for team in sorted(stats.keys(), key=lambda t: (-stats[t]['wins'], stats[t]['losses'])):
        s = stats[team]
        print(f"\n{team} ({s['division']}) - Matrix Rank: {s['matrix_rank']}")
        print(f"  Record: {s['wins']}-{s['losses']}-{s['ties']}")
        print(f"  Division: {s['division_wins']}-{s['division_losses']}-{s['division_ties']}")
        print(f"  Points: {s['points_for']} for, {s['points_against']} against")
    
    # Save all data
    # Remove non-serializable game references
    stats_for_save = {}
    for team, s in stats.items():
        stats_for_save[team] = {k: v for k, v in s.items() if k != 'games_played'}
    
    data = {
        'games': played_games,
        'stats': stats_for_save,
        'divisions': DIVISIONS,
        'teams': ALL_TEAMS,
        'matrix_ranks': matrix_ranks,
        'week14_matchups': week14_matchups,
    }
    
    with open('full_history.json', 'w') as f:
        json.dump(data, f, indent=2)
    
    print("\n✅ Full history saved to full_history.json")
    
    return data

if __name__ == "__main__":
    main()
