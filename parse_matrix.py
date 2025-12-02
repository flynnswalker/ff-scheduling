#!/usr/bin/env python3
"""
Parse the Power Matrix detailed records from the FFPL website.
Format: HOME team (row) vs VISITOR team (column) = home team record
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

# Team abbreviations from the matrix
ABBREV_TO_FULL = {
    'BB': "Boomie's Boys",
    'HHB': "Hampden Has-Beens",
    'MS': "Mobius Strippers",
    'OD2': "One Direction Two",
    'GG': "Gashouse Gorillas",
    'LPH': "Los Pollos Hermanos",
    'TRB': "The ReBiggulators",
    'YY': "Ytterby Yetis",
    'ESB': "East Shore Boys",
    'FtN': "Free The Nip",
    'LP': "Lester Pearls",
    'TOS': "The Original Series",
}

FULL_TO_ABBREV = {v: k for k, v in ABBREV_TO_FULL.items()}

# Column order from the matrix header
COLUMN_ORDER = ['BB', 'HHB', 'MS', 'OD2', 'GG', 'LPH', 'TRB', 'YY', 'ESB', 'FtN', 'LP', 'TOS']

# Row order (home teams)
ROW_ORDER = [
    "Boomie's Boys",
    "Hampden Has-Beens",
    "Mobius Strippers",
    "One Direction Two",
    "Gashouse Gorillas",
    "Los Pollos Hermanos",
    "The ReBiggulators",
    "Ytterby Yetis",
    "East Shore Boys",
    "Free The Nip",
    "Lester Pearls",
    "The Original Series",
]


def parse_record(record_str):
    """Parse a record string like '5-7-1' or '10-3' into (wins, losses, ties)."""
    if not record_str or record_str.strip() == '':
        return None
    
    record_str = record_str.strip()
    
    # Must match pattern like "5-7" or "5-7-1"
    match = re.match(r'^(\d+)-(\d+)(?:-(\d+))?$', record_str)
    if not match:
        return None
    
    wins = int(match.group(1))
    losses = int(match.group(2))
    ties = int(match.group(3)) if match.group(3) else 0
    
    return wins, losses, ties


def get_detailed_records():
    """Fetch and parse the detailed Power Matrix records."""
    session = requests.Session()
    session.headers.update(HEADERS)
    
    url = f"{BASE_URL}/FFL.cfm?FID=Matrix.cfm&MatID=3&League={LEAGUE_ID}"
    resp = session.get(url, timeout=10)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # Find all the data rows - look for rows with team names
    all_rows = soup.find_all('tr')
    
    matrix = {}  # {(home_team, away_team): (home_wins, home_losses, home_ties)}
    
    for row in all_rows:
        cells = row.find_all(['td', 'th'])
        
        # Look for rows that have a team name in the first cell
        if len(cells) < 13:
            continue
            
        first_cell = cells[0].get_text(strip=True)
        
        # Check if this is a data row (has a team name)
        home_team = None
        for full_name in ROW_ORDER:
            if full_name.replace("'", "`") in first_cell or first_cell in full_name:
                home_team = full_name
                break
        
        if home_team is None:
            continue
        
        # Parse the record cells (columns 1-12 are the opponents)
        for i, abbrev in enumerate(COLUMN_ORDER):
            if i + 1 >= len(cells):
                continue
                
            away_team = ABBREV_TO_FULL[abbrev]
            
            if away_team == home_team:
                continue
            
            record_text = cells[i + 1].get_text(strip=True)
            record = parse_record(record_text)
            
            if record:
                matrix[(home_team, away_team)] = record
    
    return matrix


def calculate_win_probability(home_team, away_team, matrix):
    """
    Calculate win probability for away_team when visiting home_team.
    The matrix stores home team records, so we flip it.
    """
    key = (home_team, away_team)
    if key not in matrix:
        return 0.5, 0.5  # Default if no data
    
    home_wins, home_losses, home_ties = matrix[key]
    
    # Away team wins = home team losses, etc.
    away_wins = home_losses
    away_losses = home_wins
    away_ties = home_ties
    
    total = away_wins + away_losses + away_ties
    if total == 0:
        return 0.5, 0.5
    
    # Treat ties as 0.5 wins for each side
    away_win_pct = (away_wins + 0.5 * away_ties) / total
    home_win_pct = (home_wins + 0.5 * home_ties) / total
    
    return away_win_pct, home_win_pct


def main():
    print("Fetching detailed Power Matrix records...")
    matrix = get_detailed_records()
    
    print(f"\nParsed {len(matrix)} matchup records\n")
    
    # Week 14 matchups (Away @ Home)
    week14_matchups = [
        ("The ReBiggulators", "Los Pollos Hermanos"),
        ("Gashouse Gorillas", "Ytterby Yetis"),
        ("Hampden Has-Beens", "One Direction Two"),
        ("Boomie's Boys", "Mobius Strippers"),
        ("The Original Series", "Free The Nip"),
        ("Lester Pearls", "East Shore Boys"),
    ]
    
    print("Week 14 Win Probabilities (from Power Matrix):")
    print("=" * 70)
    
    matchup_probs = {}
    
    for away, home in week14_matchups:
        key = (home, away)
        if key in matrix:
            home_wins, home_losses, home_ties = matrix[key]
            away_win_pct, home_win_pct = calculate_win_probability(home, away, matrix)
            
            print(f"\n{away} @ {home}:")
            print(f"  Home record (from matrix): {home_wins}-{home_losses}-{home_ties}")
            print(f"  {away} win: {away_win_pct*100:.1f}%")
            print(f"  {home} win: {home_win_pct*100:.1f}%")
            
            matchup_probs[(away, home)] = {
                'away_win_pct': away_win_pct,
                'home_win_pct': home_win_pct,
                'home_record': f"{home_wins}-{home_losses}-{home_ties}",
            }
        else:
            print(f"\n{away} @ {home}: NO DATA FOUND")
    
    # Save to JSON
    output = {
        'matchup_probs': {f"{away}__at__{home}": data for (away, home), data in matchup_probs.items()},
        'matrix': {f"{home}__vs__{away}": {'wins': w, 'losses': l, 'ties': t} 
                   for (home, away), (w, l, t) in matrix.items()},
    }
    
    with open('power_matrix_probs.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print("\n\n✅ Saved to power_matrix_probs.json")


if __name__ == "__main__":
    main()

