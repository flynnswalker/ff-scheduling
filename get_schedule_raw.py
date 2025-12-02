#!/usr/bin/env python3
"""
Get raw schedule HTML to debug parsing.
"""

import requests
from bs4 import BeautifulSoup
import re

BASE_URL = "https://www.dougin.com/ffl"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

session = requests.Session()
session.headers.update(HEADERS)

url = f"{BASE_URL}/FFL.cfm?FID=LeagueSchedule.cfm&League=3"
resp = session.get(url, timeout=10)

# Save raw HTML
with open('schedule_raw.html', 'w') as f:
    f.write(resp.text)

print("Saved raw HTML to schedule_raw.html")

# Parse and look for Week 14 specifically
soup = BeautifulSoup(resp.text, 'html.parser')

# Get text and look for unplayed games (no scores)
text = soup.get_text()
text = re.sub(r'\s+', ' ', text)

# Find Week 14 section specifically
print("\n" + "="*60)
print("Looking for Week 14...")
print("="*60)

# Find position of "Week 14" and "Week 15" or similar
week14_start = text.find('Week 14')
week15_start = text.find('Week 15')
playoff_start = text.find('Playoff')

print(f"Week 14 starts at: {week14_start}")
print(f"Week 15 starts at: {week15_start}")
print(f"Playoff starts at: {playoff_start}")

if week14_start > 0:
    # Find end of week 14
    end_pos = len(text)
    if week15_start > week14_start:
        end_pos = week15_start
    elif playoff_start > week14_start:
        end_pos = playoff_start
    
    week14_text = text[week14_start:end_pos]
    print(f"\nWeek 14 section ({len(week14_text)} chars):")
    print("-"*60)
    print(week14_text)
    print("-"*60)

# Also look for patterns without scores (unplayed games)
print("\n" + "="*60)
print("Looking for unplayed matchups (no scores in parentheses)")
print("="*60)

# Unplayed games pattern: "Team1 at Team2" without (score)
unplayed_pattern = r'([A-Z][a-zA-Z`\'\s]+?)\s+at\s+([A-Z][a-zA-Z`\'\s]+?)(?=\s+[A-Z]|\s*$)'

# Get matches from end of schedule
end_text = text[-3000:]  # Last 3000 chars should have Week 14
print("\nLast part of schedule:")
print(end_text)

