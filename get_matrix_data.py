#!/usr/bin/env python3
"""
Fetch Power Matrix data to calculate win probabilities for each matchup.

The Power Matrix shows hypothetical outcomes if every team played every other team each week.
We can use this to calculate win probabilities for Week 14 matchups.
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

def normalize_team_name(name):
    """Normalize team name."""
    name = name.strip().replace('`', "'")
    
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


def get_weekly_scores():
    """
    Get each team's score for each week from the schedule.
    Returns dict: {team: {week: score}}
    """
    session = requests.Session()
    session.headers.update(HEADERS)
    
    url = f"{BASE_URL}/FFL.cfm?FID=LeagueSchedule.cfm&League={LEAGUE_ID}"
    resp = session.get(url, timeout=10)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # Find all game links with scores
    game_links = soup.find_all('a', class_='base_link2')
    
    weekly_scores = {team: {} for team in ALL_TEAMS}
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
            
            if away_team in ALL_TEAMS and home_team in ALL_TEAMS:
                week = (game_count // 6) + 1
                
                weekly_scores[away_team][week] = away_score
                weekly_scores[home_team][week] = home_score
                
                game_count += 1
    
    return weekly_scores


def calculate_matrix_records(weekly_scores):
    """
    Calculate the Power Matrix record for each team pair.
    
    For each week, compare every team's score against every other team.
    Returns dict: {(team1, team2): {'wins': X, 'losses': Y, 'ties': Z}}
    """
    matrix = {}
    
    for team1 in ALL_TEAMS:
        for team2 in ALL_TEAMS:
            if team1 != team2:
                wins = 0
                losses = 0
                ties = 0
                
                # Compare scores for each week both teams have scores
                for week in range(1, 14):
                    if week in weekly_scores[team1] and week in weekly_scores[team2]:
                        score1 = weekly_scores[team1][week]
                        score2 = weekly_scores[team2][week]
                        
                        if score1 > score2:
                            wins += 1
                        elif score2 > score1:
                            losses += 1
                        else:
                            ties += 1
                
                matrix[(team1, team2)] = {
                    'wins': wins,
                    'losses': losses,
                    'ties': ties,
                    'total': wins + losses + ties,
                    'win_pct': wins / (wins + losses + ties) if (wins + losses + ties) > 0 else 0.5
                }
    
    return matrix


def main():
    print("Fetching weekly scores...")
    weekly_scores = get_weekly_scores()
    
    print("\nWeekly scores by team:")
    for team in ALL_TEAMS:
        scores = weekly_scores[team]
        print(f"  {team}: {len(scores)} weeks - {list(scores.values())}")
    
    print("\nCalculating Power Matrix records...")
    matrix = calculate_matrix_records(weekly_scores)
    
    # Show Week 14 matchup probabilities
    week14_matchups = [
        ("The ReBiggulators", "Los Pollos Hermanos"),
        ("Gashouse Gorillas", "Ytterby Yetis"),
        ("Hampden Has-Beens", "One Direction Two"),
        ("Boomie's Boys", "Mobius Strippers"),
        ("The Original Series", "Free The Nip"),
        ("Lester Pearls", "East Shore Boys"),
    ]
    
    print("\nWeek 14 Win Probabilities (based on Power Matrix):")
    print("-" * 60)
    
    for away, home in week14_matchups:
        away_record = matrix[(away, home)]
        home_record = matrix[(home, away)]
        
        print(f"\n{away} at {home}:")
        print(f"  {away}: {away_record['wins']}-{away_record['losses']}-{away_record['ties']} ({away_record['win_pct']*100:.1f}%)")
        print(f"  {home}: {home_record['wins']}-{home_record['losses']}-{home_record['ties']} ({home_record['win_pct']*100:.1f}%)")
    
    # Save matrix data
    # Convert tuple keys to strings for JSON
    matrix_json = {}
    for (t1, t2), data in matrix.items():
        key = f"{t1}__vs__{t2}"
        matrix_json[key] = data
    
    output = {
        'weekly_scores': weekly_scores,
        'matrix': matrix_json,
    }
    
    with open('matrix_data.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print("\n✅ Matrix data saved to matrix_data.json")


if __name__ == "__main__":
    main()

