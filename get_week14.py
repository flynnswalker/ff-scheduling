#!/usr/bin/env python3
"""
Get Week 14 matchups and current standings for playoff scenario analysis.
"""

import requests
from bs4 import BeautifulSoup
import re
import json

# Configuration
BASE_URL = "https://www.dougin.com/ffl"
LEAGUE_URL = f"{BASE_URL}/ffl.cfm?League=3"

# Use a browser-like User-Agent
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
}

def create_session():
    """Create session with browser headers."""
    session = requests.Session()
    session.headers.update(HEADERS)
    return session

def get_standings(session):
    """Get current standings from Power Matrix."""
    print("=" * 60)
    print("CURRENT STANDINGS")
    print("=" * 60)
    
    url = f"{BASE_URL}/FFL.cfm?Matrix=1&League=3"
    resp = session.get(url, timeout=10)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # Find the standings table
    tables = soup.find_all('table')
    
    standings = []
    
    for table in tables:
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all(['th', 'td'])
            cell_texts = [c.get_text(strip=True) for c in cells]
            
            # Look for rows that look like standings (have rank, team name, record)
            if len(cell_texts) >= 4:
                # Check if first cell looks like a rank (e.g., "1.", "2.")
                first = cell_texts[0]
                if re.match(r'^\d+\.', first):
                    rank = first.replace('.', '')
                    standings.append(cell_texts)
    
    # Parse standings
    parsed_standings = []
    for row in standings:
        try:
            # Format: Rank, Prev, Team, Div, Record1, Pct1, Record2, Pct2, Record3, Pct3, Performance
            rank = row[0].replace('.', '')
            prev_rank = row[1]
            team = row[2]
            div = row[3]
            
            # Power record (total points)
            power_record = row[4]  # e.g., "225-57-4"
            power_pct = row[5]  # e.g., "0.794"
            
            # H2H Record
            h2h_record = row[6]  # e.g., "10.6-3.4"
            h2h_pct = row[7]  # e.g., "0.757"
            
            # Projected Record
            proj_record = row[8]  # e.g., "10-3"
            proj_pct = row[9]  # e.g., "0.769"
            
            parsed = {
                'rank': int(rank),
                'prev_rank': int(prev_rank) if prev_rank.isdigit() else prev_rank,
                'team': team,
                'division': div,
                'power_record': power_record,
                'power_pct': float(power_pct),
                'h2h_record': h2h_record,
                'h2h_pct': float(h2h_pct),
                'weekly_record': proj_record,  # This is the W-L record
                'weekly_pct': float(proj_pct),
            }
            parsed_standings.append(parsed)
            print(f"{rank:2}. {team:25} ({div}) - W-L: {proj_record:5} ({proj_pct})")
            
        except (IndexError, ValueError) as e:
            continue
    
    return parsed_standings

def get_full_schedule(session):
    """Get the full schedule including Week 14."""
    print("\n" + "=" * 60)
    print("FULL SCHEDULE")
    print("=" * 60)
    
    url = f"{BASE_URL}/FFL.cfm?FID=LeagueSchedule.cfm&League=3"
    resp = session.get(url, timeout=10)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    text = soup.get_text()
    
    # Split by weeks
    weeks = re.split(r'Week\s*(\d+)', text)
    
    schedule = {}
    
    i = 1
    while i < len(weeks) - 1:
        week_num = int(weeks[i])
        week_content = weeks[i + 1]
        
        # Parse matchups
        # Format: "Team1 (score1) at Team2 (score2)" or "Team1 at Team2" for unplayed
        matchup_pattern = r'([A-Za-z`\'\s]+?)\s*(?:\((\d+)\))?\s*at\s*([A-Za-z`\'\s]+?)\s*(?:\((\d+)\))?(?=\s*(?:[A-Z]|$))'
        
        matchups = []
        
        # Simpler parsing - look for "at" pattern
        lines = week_content.strip().split('\n')
        current_text = ' '.join(lines)
        
        # Find all "X at Y" patterns
        parts = re.split(r'\s+at\s+', current_text)
        
        if week_num <= 14:
            schedule[week_num] = week_content.strip()[:500]  # Store raw for debugging
        
        i += 2
    
    return schedule

def get_week14_matchups(session):
    """Get Week 14 matchups specifically."""
    print("\n" + "=" * 60)
    print("WEEK 14 MATCHUPS")
    print("=" * 60)
    
    url = f"{BASE_URL}/FFL.cfm?FID=LeagueSchedule.cfm&League=3"
    resp = session.get(url, timeout=10)
    
    # Find Week 14 section
    text = resp.text
    
    # Look for Week 14
    match = re.search(r'Week\s*14(.*?)(?:Week\s*15|Playoff|$)', text, re.DOTALL | re.IGNORECASE)
    
    if match:
        week14_html = match.group(1)
        soup = BeautifulSoup(week14_html, 'html.parser')
        week14_text = soup.get_text()
        
        print("Week 14 content:")
        print(week14_text[:1000])
        
        # Parse matchups
        matchups = []
        
        # Pattern: "Away Team (score) at Home Team (score)" or without scores
        # The scores might be in parentheses
        pattern = r'([A-Za-z`\'\s]+?)\s*(?:\((\d+)\))?\s*at\s*([A-Za-z`\'\s]+?)\s*(?:\((\d+)\))?'
        
        matches = re.findall(pattern, week14_text)
        
        for m in matches:
            away = m[0].strip()
            away_score = m[1] if m[1] else None
            home = m[2].strip()
            home_score = m[3] if m[3] else None
            
            # Filter out garbage
            if len(away) > 3 and len(home) > 3:
                matchups.append({
                    'away': away,
                    'away_score': int(away_score) if away_score else None,
                    'home': home,
                    'home_score': int(home_score) if home_score else None
                })
        
        print("\nParsed matchups:")
        for m in matchups:
            if m['away_score']:
                print(f"  {m['away']} ({m['away_score']}) at {m['home']} ({m['home_score']})")
            else:
                print(f"  {m['away']} at {m['home']}")
        
        return matchups
    else:
        print("Could not find Week 14 in schedule")
        return []

def parse_schedule_better(session):
    """Better schedule parsing."""
    print("\n" + "=" * 60)
    print("DETAILED SCHEDULE PARSING")
    print("=" * 60)
    
    url = f"{BASE_URL}/FFL.cfm?FID=LeagueSchedule.cfm&League=3"
    resp = session.get(url, timeout=10)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # Get all text
    full_text = soup.get_text()
    
    # Clean up whitespace
    full_text = re.sub(r'\s+', ' ', full_text)
    
    # Find all weeks
    all_weeks = {}
    
    for week_num in range(1, 15):
        pattern = rf'Week\s*{week_num}\s*(.*?)(?=Week\s*{week_num+1}|Playoff|$)'
        match = re.search(pattern, full_text, re.IGNORECASE)
        
        if match:
            week_content = match.group(1)
            
            # Parse individual matchups
            # Teams are separated by "at"
            # Each matchup ends when a new team name starts (capital letter after score/space)
            
            matchups = []
            
            # Split on " at " and process pairs
            parts = week_content.split(' at ')
            
            for i in range(len(parts) - 1):
                # The away team is at the end of parts[i]
                # The home team is at the start of parts[i+1]
                
                # Get away team (last team name in parts[i])
                away_match = re.search(r'([A-Z][a-z`\']+(?:\s+[A-Za-z`\']+)*)\s*(?:\((\d+)\))?\s*$', parts[i])
                
                # Get home team (first team name in parts[i+1])
                home_match = re.search(r'^([A-Z][a-z`\']+(?:\s+[A-Za-z`\']+)*)\s*(?:\((\d+)\))?', parts[i+1])
                
                if away_match and home_match:
                    away_team = away_match.group(1).strip()
                    away_score = away_match.group(2)
                    home_team = home_match.group(1).strip()
                    home_score = home_match.group(2)
                    
                    if len(away_team) > 3 and len(home_team) > 3:
                        matchups.append({
                            'away': away_team,
                            'away_score': int(away_score) if away_score else None,
                            'home': home_team,
                            'home_score': int(home_score) if home_score else None
                        })
            
            all_weeks[week_num] = matchups
    
    # Print Week 13 and 14
    for week in [13, 14]:
        if week in all_weeks:
            print(f"\nWeek {week}:")
            for m in all_weeks[week]:
                if m['away_score'] is not None:
                    print(f"  {m['away']} ({m['away_score']}) at {m['home']} ({m['home_score']})")
                else:
                    print(f"  {m['away']} at {m['home']} (not played)")
    
    return all_weeks

def main():
    session = create_session()
    
    # Get current standings
    standings = get_standings(session)
    
    # Get full schedule
    schedule = parse_schedule_better(session)
    
    # Save data for later use
    data = {
        'standings': standings,
        'schedule': {str(k): v for k, v in schedule.items()}
    }
    
    with open('league_data.json', 'w') as f:
        json.dump(data, f, indent=2)
    
    print("\n" + "=" * 60)
    print("Data saved to league_data.json")
    print("=" * 60)

if __name__ == "__main__":
    main()

