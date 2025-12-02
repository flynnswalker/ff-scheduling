#!/usr/bin/env python3
"""
League data extraction for FFPL fantasy football league.
Successfully tested access to https://www.dougin.com/ffl/ffl.cfm?League=3
"""

import requests
from bs4 import BeautifulSoup
import re
import json

# Configuration
BASE_URL = "https://www.dougin.com/ffl"
LEAGUE_ID = 3
LEAGUE_URL = f"{BASE_URL}/ffl.cfm?League={LEAGUE_ID}"

# Browser-like headers (required for site access)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
}

# All team names in the league
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

def normalize_team_name(name):
    """Normalize team name variations."""
    name = name.strip()
    # Handle backtick vs apostrophe
    name = name.replace('`', "'")
    return name


class FFPLScraper:
    """Scraper for FFPL fantasy football league data."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
    
    def get_standings(self):
        """Get current standings from Power Matrix."""
        url = f"{BASE_URL}/FFL.cfm?Matrix=1&League={LEAGUE_ID}"
        resp = self.session.get(url, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Find tables
        tables = soup.find_all('table')
        
        standings = []
        
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['th', 'td'])
                cell_texts = [c.get_text(strip=True) for c in cells]
                
                # Look for rows starting with rank (e.g., "1.", "2.")
                if len(cell_texts) >= 10:
                    first = cell_texts[0]
                    if re.match(r'^\d+\.$', first):
                        try:
                            rank = int(first.replace('.', ''))
                            prev_rank = int(cell_texts[1]) if cell_texts[1].isdigit() else rank
                            team = normalize_team_name(cell_texts[2])
                            div = cell_texts[3]
                            
                            # Weekly record is in position 8 (e.g., "10-3")
                            weekly_record = cell_texts[8]
                            
                            if '-' in weekly_record:
                                parts = weekly_record.split('-')
                                wins = int(parts[0])
                                losses = int(parts[1])
                                
                                standings.append({
                                    'rank': rank,
                                    'prev_rank': prev_rank,
                                    'team': team,
                                    'division': div,
                                    'wins': wins,
                                    'losses': losses,
                                    'weekly_record': weekly_record,
                                })
                        except (ValueError, IndexError):
                            continue
        
        # Remove duplicates
        seen = set()
        unique_standings = []
        for s in standings:
            if s['team'] not in seen:
                seen.add(s['team'])
                unique_standings.append(s)
        
        return unique_standings
    
    def get_week14_matchups(self):
        """Get Week 14 matchups."""
        url = f"{BASE_URL}/FFL.cfm?FID=LeagueSchedule.cfm&League={LEAGUE_ID}"
        resp = self.session.get(url, timeout=10)
        
        text = resp.text
        text_clean = re.sub(r'\s+', ' ', text)
        
        # Find Week 14 section (games without scores)
        week14_match = re.search(r'Week 14\s*(.*?)(?:Playoffs?|Championship|I\'m a dialog|$)', text_clean, re.IGNORECASE)
        
        matchups = []
        
        if week14_match:
            week14_text = week14_match.group(1)
            
            # Week 14 games have no scores, format: "Team1 at Team2 Team3 at Team4..."
            # Split by "at" and pair consecutive teams
            parts = re.split(r'\s+at\s+', week14_text)
            
            for i in range(len(parts) - 1):
                # The away team is at the end of parts[i]
                # The home team is at the start of parts[i+1]
                
                away = parts[i].strip()
                home = parts[i + 1].strip()
                
                # Get just the last team name from away (might have previous home team)
                for team in ALL_TEAMS:
                    team_pattern = team.replace("'", "[`']")
                    if re.search(rf'{team_pattern}$', away, re.IGNORECASE):
                        away = team
                        break
                
                # Get just the first team name from home
                for team in ALL_TEAMS:
                    team_pattern = team.replace("'", "[`']")
                    if re.search(rf'^{team_pattern}', home, re.IGNORECASE):
                        home = team
                        break
                
                if away in ALL_TEAMS and home in ALL_TEAMS:
                    matchups.append({
                        'away': away,
                        'home': home
                    })
        
        return matchups
    
    def get_all_data(self):
        """Get all league data needed for scenario analysis."""
        standings = self.get_standings()
        matchups = self.get_week14_matchups()
        
        return {
            'standings': standings,
            'week14_matchups': matchups,
            'teams': ALL_TEAMS,
            'divisions': DIVISIONS,
        }


def main():
    print("=" * 60)
    print("FFPL League Data Extraction")
    print("=" * 60)
    
    scraper = FFPLScraper()
    data = scraper.get_all_data()
    
    print("\n📊 CURRENT STANDINGS (after Week 13):")
    print("-" * 50)
    for s in data['standings']:
        print(f"  {s['rank']:2}. {s['team']:25} ({s['division']}) {s['wins']:2}-{s['losses']}")
    
    print("\n📅 WEEK 14 MATCHUPS:")
    print("-" * 50)
    for m in data['week14_matchups']:
        print(f"  {m['away']:25} at {m['home']}")
    
    print("\n🏈 DIVISIONS:")
    print("-" * 50)
    for div, teams in data['divisions'].items():
        print(f"  Division {div}: {', '.join(teams)}")
    
    # Save data
    with open('ffpl_data.json', 'w') as f:
        json.dump(data, f, indent=2)
    
    print("\n✅ Data saved to ffpl_data.json")
    
    return data


if __name__ == "__main__":
    main()
