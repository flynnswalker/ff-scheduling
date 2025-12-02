#!/usr/bin/env python3
"""
Fetch data for all 3 Walker FFL leagues: WFFL, DFFL, FFPL
"""

import requests
from bs4 import BeautifulSoup
import re
import json
from collections import defaultdict

BASE_URL = "https://www.dougin.com/ffl"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

LEAGUES = {
    'WFFL': {'id': 1, 'has_relegation': False},
    'DFFL': {'id': 2, 'has_relegation': False},
    'FFPL': {'id': 3, 'has_relegation': True},
}


def normalize_team_name(name):
    """Normalize team name by cleaning up special characters."""
    return name.strip().replace('`', "'")


def get_teams_and_divisions(league_id):
    """Get team names and division assignments from the standings page."""
    session = requests.Session()
    session.headers.update(HEADERS)
    
    url = f"{BASE_URL}/FFL.cfm?League={league_id}"
    resp = session.get(url, timeout=10)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    teams = []
    divisions = {'O': [], 'W': [], 'D': []}
    
    # Find team links in the menu
    team_menu = soup.find_all('a', onclick=re.compile(r'mainMenu\(0,\d+\)'))
    for link in team_menu:
        team_name = normalize_team_name(link.get_text(strip=True))
        if team_name and team_name != 'Sith Lords':  # Skip inactive teams
            teams.append(team_name)
    
    return teams, divisions


def get_standings_and_divisions(league_id):
    """Get current standings with division info from the Power Matrix page."""
    session = requests.Session()
    session.headers.update(HEADERS)
    
    url = f"{BASE_URL}/FFL.cfm?Matrix=1&League={league_id}"
    resp = session.get(url, timeout=10)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    teams = []
    divisions = {}  # Dynamically populated
    stats = {}
    matrix_ranks = {}
    
    # Find the standings table rows
    rows = soup.find_all('tr')
    rank = 0
    
    for row in rows:
        cells = row.find_all(['td', 'th'])
        if len(cells) >= 10:
            # Look for rows with team links
            team_link = row.find('a', class_='base_link2')
            if team_link:
                rank += 1
                team_name = normalize_team_name(team_link.get_text(strip=True))
                
                # Find division cell - single letter cell (O, W, D, S, H, etc.)
                div_cell = None
                for i, cell in enumerate(cells):
                    text = cell.get_text(strip=True)
                    # Division is a single uppercase letter
                    if len(text) == 1 and text.isupper():
                        div_cell = text
                        break
                
                if team_name and team_name not in teams:
                    teams.append(team_name)
                    if div_cell:
                        if div_cell not in divisions:
                            divisions[div_cell] = []
                        if team_name not in divisions[div_cell]:
                            divisions[div_cell].append(team_name)
                    matrix_ranks[team_name] = rank
                    
                    # Initialize stats (will be filled from schedule)
                    stats[team_name] = {
                        'wins': 0, 'losses': 0, 'ties': 0,
                        'division_wins': 0, 'division_losses': 0, 'division_ties': 0,
                        'points_for': 0, 'points_against': 0,
                        'matrix_rank': rank,
                        'h2h': defaultdict(lambda: {'wins': 0, 'losses': 0, 'ties': 0, 'points_for': 0, 'points_against': 0})
                    }
    
    return teams, divisions, stats, matrix_ranks


def get_schedule_and_stats(league_id, teams, divisions):
    """Get full schedule and calculate stats from game results."""
    session = requests.Session()
    session.headers.update(HEADERS)
    
    url = f"{BASE_URL}/FFL.cfm?FID=LeagueSchedule.cfm&League={league_id}"
    resp = session.get(url, timeout=10)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    stats = {team: {
        'wins': 0, 'losses': 0, 'ties': 0,
        'division_wins': 0, 'division_losses': 0, 'division_ties': 0,
        'points_for': 0, 'points_against': 0,
        'matrix_rank': 0,
        'h2h': {opp: {'wins': 0, 'losses': 0, 'ties': 0, 'points_for': 0, 'points_against': 0} 
                for opp in teams if opp != team}
    } for team in teams}
    
    week14_matchups = []
    played_games = []
    
    # Find all game links (played games)
    game_links = soup.find_all('a', class_='base_link2')
    
    game_count = 0
    for link in game_links:
        game_text = link.get_text(strip=True)
        
        # Pattern for played games: "Team1 (score1) at Team2 (score2)"
        played_match = re.match(r'(.+?)\s*\((\d+)\)\s*at\s*(.+?)\s*\((\d+)\)', game_text)
        
        if played_match:
            away_team = normalize_team_name(played_match.group(1))
            away_score = int(played_match.group(2))
            home_team = normalize_team_name(played_match.group(3))
            home_score = int(played_match.group(4))
            
            if away_team in teams and home_team in teams:
                game_count += 1
                week = (game_count - 1) // 6 + 1
                
                # Determine division game
                away_div = None
                home_div = None
                for div, div_teams in divisions.items():
                    if away_team in div_teams:
                        away_div = div
                    if home_team in div_teams:
                        home_div = div
                is_div_game = away_div == home_div and away_div is not None
                
                played_games.append({
                    'week': week,
                    'away_team': away_team,
                    'away_score': away_score,
                    'home_team': home_team,
                    'home_score': home_score,
                    'is_division_game': is_div_game
                })
                
                # Update stats
                if away_score > home_score:
                    stats[away_team]['wins'] += 1
                    stats[home_team]['losses'] += 1
                    stats[away_team]['h2h'][home_team]['wins'] += 1
                    stats[home_team]['h2h'][away_team]['losses'] += 1
                    if is_div_game:
                        stats[away_team]['division_wins'] += 1
                        stats[home_team]['division_losses'] += 1
                elif home_score > away_score:
                    stats[home_team]['wins'] += 1
                    stats[away_team]['losses'] += 1
                    stats[home_team]['h2h'][away_team]['wins'] += 1
                    stats[away_team]['h2h'][home_team]['losses'] += 1
                    if is_div_game:
                        stats[home_team]['division_wins'] += 1
                        stats[away_team]['division_losses'] += 1
                else:
                    stats[away_team]['ties'] += 1
                    stats[home_team]['ties'] += 1
                    stats[away_team]['h2h'][home_team]['ties'] += 1
                    stats[home_team]['h2h'][away_team]['ties'] += 1
                    if is_div_game:
                        stats[away_team]['division_ties'] += 1
                        stats[home_team]['division_ties'] += 1
                
                stats[away_team]['points_for'] += away_score
                stats[away_team]['points_against'] += home_score
                stats[home_team]['points_for'] += home_score
                stats[home_team]['points_against'] += away_score
                
                stats[away_team]['h2h'][home_team]['points_for'] += away_score
                stats[away_team]['h2h'][home_team]['points_against'] += home_score
                stats[home_team]['h2h'][away_team]['points_for'] += home_score
                stats[home_team]['h2h'][away_team]['points_against'] += away_score
    
    # Find Week 14 matchups - these are plain text in <td> elements (not links)
    # Look for td cells under Week 14 header
    all_tds = soup.find_all('td', align='center')
    for td in all_tds:
        text = td.get_text(strip=True)
        # Unplayed games don't have score parentheses like "(35)"
        # But they may have parentheses in team names like "(university)"
        # Check: has " at " but no pattern like "(number)"
        if ' at ' in text and not re.search(r'\(\d+\)', text):
            unplayed_match = re.match(r'(.+?)\s+at\s+(.+?)$', text)
            if unplayed_match:
                away_raw = unplayed_match.group(1).replace('`', "'").strip()
                home_raw = unplayed_match.group(2).replace('`', "'").strip()
                
                # Find matching team names
                away_team = None
                home_team = None
                for team in teams:
                    if team == away_raw or team in away_raw or away_raw in team:
                        away_team = team
                    if team == home_raw or team in home_raw or home_raw in team:
                        home_team = team
                
                if away_team and home_team and away_team in teams and home_team in teams:
                    # Determine division game
                    away_div = None
                    home_div = None
                    for div, div_teams in divisions.items():
                        if away_team in div_teams:
                            away_div = div
                        if home_team in div_teams:
                            home_div = div
                    is_div_game = away_div == home_div and away_div is not None
                    
                    # Avoid duplicates
                    if not any(m['away_team'] == away_team and m['home_team'] == home_team for m in week14_matchups):
                        week14_matchups.append({
                            'away_team': away_team,
                            'home_team': home_team,
                            'is_division_game': is_div_game
                        })
    
    return stats, week14_matchups, played_games


def get_power_matrix_probs(league_id, teams):
    """Get detailed Power Matrix records for win probability calculation."""
    session = requests.Session()
    session.headers.update(HEADERS)
    
    url = f"{BASE_URL}/FFL.cfm?FID=Matrix.cfm&MatID=3&League={league_id}"
    resp = session.get(url, timeout=10)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    matrix = {}  # {(home_team, away_team): (home_wins, home_losses, home_ties)}
    
    # Find all data rows
    all_rows = soup.find_all('tr')
    
    # Build column order from header
    column_teams = []
    for row in all_rows:
        header_cells = row.find_all('th')
        for cell in header_cells:
            text = cell.get_text(strip=True)
            # Look for abbreviation patterns (2-4 uppercase letters)
            if re.match(r'^[A-Z][A-Za-z0-9]{1,4}$', text) and text not in ['HOME', 'Rank', 'Prev', 'Team', 'Div', 'Pct', 'Record']:
                column_teams.append(text)
        if len(column_teams) >= 12:
            break
    
    # Now find data rows and parse records
    for row in all_rows:
        cells = row.find_all(['td', 'th'])
        if len(cells) < 13:
            continue
        
        # First cell should be team name
        first_cell_text = cells[0].get_text(strip=True)
        home_team = None
        
        for team in teams:
            if team.replace("'", "`") in first_cell_text or first_cell_text.replace("`", "'") == team:
                home_team = team
                break
        
        if home_team is None:
            continue
        
        # Parse record cells
        for i, cell in enumerate(cells[1:13]):
            if i >= len(column_teams):
                break
            
            record_text = cell.get_text(strip=True)
            match = re.match(r'^(\d+)-(\d+)(?:-(\d+))?$', record_text)
            
            if match:
                wins = int(match.group(1))
                losses = int(match.group(2))
                ties = int(match.group(3)) if match.group(3) else 0
                
                # We need to map column abbreviation to full team name
                # For now, store with index
                matrix[(home_team, i)] = (wins, losses, ties)
    
    return matrix, column_teams


def get_matrix_ranks(league_id, teams):
    """Get matrix ranks from the Power Matrix standings."""
    session = requests.Session()
    session.headers.update(HEADERS)
    
    url = f"{BASE_URL}/FFL.cfm?Matrix=1&League={league_id}"
    resp = session.get(url, timeout=10)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    matrix_ranks = {}
    rows = soup.find_all('tr')
    
    for row in rows:
        cells = row.find_all(['td', 'th'])
        if len(cells) >= 2:
            # Look for rank number in first cell
            first_text = cells[0].get_text(strip=True)
            rank_match = re.match(r'^(\d+)\.$', first_text)
            
            if rank_match:
                rank = int(rank_match.group(1))
                # Find team link in this row
                team_link = row.find('a', class_='base_link2')
                if team_link:
                    team_name = normalize_team_name(team_link.get_text(strip=True))
                    if team_name in teams:
                        matrix_ranks[team_name] = rank
    
    return matrix_ranks


def fetch_league_data(league_name, league_id):
    """Fetch all data for a single league."""
    print(f"\n{'='*60}")
    print(f"Fetching {league_name} (League {league_id})...")
    print('='*60)
    
    # Get teams and divisions from Power Matrix page
    print("  Getting standings and divisions...")
    teams, divisions, _, _ = get_standings_and_divisions(league_id)
    print(f"  Found {len(teams)} teams")
    
    # Get schedule and calculate stats
    print("  Getting schedule and stats...")
    stats, week14_matchups, played_games = get_schedule_and_stats(league_id, teams, divisions)
    print(f"  Found {len(played_games)} played games, {len(week14_matchups)} Week 14 matchups")
    
    # Get matrix ranks
    print("  Getting Power Matrix ranks...")
    matrix_ranks = get_matrix_ranks(league_id, teams)
    for team in teams:
        if team in matrix_ranks:
            stats[team]['matrix_rank'] = matrix_ranks[team]
    
    return {
        'teams': teams,
        'divisions': divisions,
        'stats': stats,
        'week14_matchups': week14_matchups,
        'played_games': played_games,
        'matrix_ranks': matrix_ranks,
    }


def fetch_matrix_probs_for_matchups(league_id, matchups, teams):
    """Fetch Power Matrix win probabilities for Week 14 matchups."""
    session = requests.Session()
    session.headers.update(HEADERS)
    
    url = f"{BASE_URL}/FFL.cfm?FID=Matrix.cfm&MatID=3&League={league_id}"
    resp = session.get(url, timeout=10)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # Find all rows
    all_rows = soup.find_all('tr')
    
    # Find the header row with column abbreviations (like BB, HHB, MS, etc.)
    column_abbrevs = []
    for row in all_rows:
        cells = row.find_all('th')
        # Look for row with many short abbreviation headers
        abbrevs = []
        for cell in cells:
            text = cell.get_text(strip=True)
            # Abbreviations: 2-5 letters/numbers, no dashes, not reserved words
            if 2 <= len(text) <= 5 and '-' not in text:
                if text not in ['HOME', 'Rank', 'Prev', 'Team', 'Pct', 'Rec', 'Div']:
                    abbrevs.append(text)
        # We want exactly 12 abbreviations (one per team)
        if len(abbrevs) == 12:
            column_abbrevs = abbrevs
            break
    
    if not column_abbrevs:
        print(f"    Warning: Could not find column abbreviations for league {league_id}")
        return {(m['away_team'], m['home_team']): {'away_win_pct': 0.5, 'home_win_pct': 0.5, 'home_record': 'N/A'} for m in matchups}
    
    # Parse data rows to extract team names and their records
    # The matrix has home teams as rows and away teams as columns
    row_data = []  # List of (team_name, [record_cells])
    matched_teams = set()  # Track which teams we've already matched
    
    for row in all_rows:
        cells = row.find_all(['td', 'th'])
        if len(cells) < len(column_abbrevs) + 1:
            continue
        
        # First cell should contain team name
        first_cell = cells[0].get_text(strip=True)
        first_cell_clean = first_cell.replace("`", "'").strip()
        
        # Check if this row has record patterns (indicates data row)
        has_records = False
        for cell in cells[1:min(6, len(cells))]:
            if re.match(r'^\d+-\d+(-\d+)?$', cell.get_text(strip=True)):
                has_records = True
                break
        
        if not has_records:
            continue
        
        # Try to match with known team names
        matched_team = None
        for team in teams:
            if team in matched_teams:
                continue
            if team == first_cell_clean:
                matched_team = team
                break
            # Try partial match only if exact match didn't work
            if first_cell_clean and len(first_cell_clean) > 5:
                if team in first_cell_clean or first_cell_clean in team:
                    matched_team = team
                    break
        
        if matched_team and matched_team not in matched_teams:
            matched_teams.add(matched_team)
            # Extract record cells
            records = []
            for i in range(1, len(column_abbrevs) + 1):
                if i < len(cells):
                    records.append(cells[i].get_text(strip=True))
                else:
                    records.append('')
            row_data.append((matched_team, records))
    
    # Build abbreviation to team name mapping based on row order
    abbrev_to_team = {}
    if len(row_data) == len(column_abbrevs):
        for i, (team_name, _) in enumerate(row_data):
            abbrev_to_team[column_abbrevs[i]] = team_name
    
    # Build the matrix: {(home_team, away_team): (home_wins, home_losses, home_ties)}
    matrix = {}
    
    for home_team, records in row_data:
        for i, abbrev in enumerate(column_abbrevs):
            if i >= len(records):
                continue
            
            away_team = abbrev_to_team.get(abbrev)
            if not away_team or away_team == home_team:
                continue
            
            record_text = records[i]
            match = re.match(r'^(\d+)-(\d+)(?:-(\d+))?$', record_text)
            
            if match:
                wins = int(match.group(1))
                losses = int(match.group(2))
                ties = int(match.group(3)) if match.group(3) else 0
                matrix[(home_team, away_team)] = (wins, losses, ties)
    
    # Calculate win probabilities for each matchup
    matchup_probs = {}
    
    for matchup in matchups:
        away = matchup['away_team']
        home = matchup['home_team']
        
        key = (home, away)
        if key in matrix:
            home_wins, home_losses, home_ties = matrix[key]
            total = home_wins + home_losses + home_ties
            if total > 0:
                away_win_pct = (home_losses + 0.5 * home_ties) / total
                home_win_pct = (home_wins + 0.5 * home_ties) / total
            else:
                away_win_pct = home_win_pct = 0.5
            
            matchup_probs[(away, home)] = {
                'away_win_pct': away_win_pct,
                'home_win_pct': home_win_pct,
                'home_record': f"{home_wins}-{home_losses}-{home_ties}" if home_ties else f"{home_wins}-{home_losses}",
            }
        else:
            matchup_probs[(away, home)] = {
                'away_win_pct': 0.5,
                'home_win_pct': 0.5,
                'home_record': 'N/A',
            }
    
    return matchup_probs


def main():
    all_data = {}
    
    for league_name, league_info in LEAGUES.items():
        league_id = league_info['id']
        
        # Fetch main data
        data = fetch_league_data(league_name, league_id)
        data['has_relegation'] = league_info['has_relegation']
        data['league_id'] = league_id
        data['league_name'] = league_name
        
        # Fetch Power Matrix probabilities for matchups
        print("  Getting Power Matrix win probabilities...")
        matchup_probs = fetch_matrix_probs_for_matchups(league_id, data['week14_matchups'], data['teams'])
        data['matchup_probs'] = {f"{away}__at__{home}": prob for (away, home), prob in matchup_probs.items()}
        
        all_data[league_name] = data
        
        div_summary = ', '.join([f"{k}={len(v)}" for k, v in sorted(data['divisions'].items())])
        print(f"\n  {league_name} Summary:")
        print(f"    Teams: {len(data['teams'])}")
        print(f"    Divisions: {div_summary}")
        print(f"    Week 14 Games: {len(data['week14_matchups'])}")
        print(f"    Has Relegation: {data['has_relegation']}")
    
    # Save all data
    output_file = 'all_leagues_data.json'
    with open(output_file, 'w') as f:
        json.dump(all_data, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"✅ All league data saved to {output_file}")
    print('='*60)


if __name__ == "__main__":
    main()

