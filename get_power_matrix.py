#!/usr/bin/env python3
"""
Fetch actual Power Matrix data from the FFPL website.
The Power Matrix shows hypothetical records for each team pair with home/away consideration.
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


def get_power_matrix_page():
    """Get the Power Matrix page HTML."""
    session = requests.Session()
    session.headers.update(HEADERS)
    
    url = f"{BASE_URL}/FFL.cfm?FID=powermatrix.cfm&League={LEAGUE_ID}"
    resp = session.get(url, timeout=10)
    return resp.text


def get_detailed_records_page():
    """Get the detailed records page if it exists."""
    session = requests.Session()
    session.headers.update(HEADERS)
    
    # Try to find the detailed records link
    urls_to_try = [
        f"{BASE_URL}/FFL.cfm?FID=powermatrix.cfm&League={LEAGUE_ID}&Detail=1",
        f"{BASE_URL}/FFL.cfm?FID=powermatrix_detail.cfm&League={LEAGUE_ID}",
        f"{BASE_URL}/FFL.cfm?FID=PowerMatrixDetail.cfm&League={LEAGUE_ID}",
    ]
    
    for url in urls_to_try:
        try:
            resp = session.get(url, timeout=10)
            if resp.status_code == 200 and len(resp.text) > 1000:
                print(f"Found detailed page at: {url}")
                return resp.text
        except:
            pass
    
    return None


def parse_power_matrix(html):
    """Parse the Power Matrix page to extract team matchup records."""
    soup = BeautifulSoup(html, 'html.parser')
    
    # Save HTML for debugging
    with open('power_matrix_raw.html', 'w') as f:
        f.write(html)
    print("Saved raw HTML to power_matrix_raw.html")
    
    # Find all links to team pages
    team_links = soup.find_all('a', href=re.compile(r'TeamPage', re.I))
    print(f"Found {len(team_links)} team links")
    
    # Look for tables with matchup data
    tables = soup.find_all('table')
    print(f"Found {len(tables)} tables")
    
    # Extract text to understand structure
    text = soup.get_text()
    
    # Look for record patterns like "7-5-1" or "5-7-1"
    record_pattern = re.compile(r'(\d+)-(\d+)-(\d+)')
    records_found = record_pattern.findall(text)
    print(f"Found {len(records_found)} record patterns")
    
    return text


def main():
    print("Fetching Power Matrix page...")
    html = get_power_matrix_page()
    
    print("\nParsing Power Matrix...")
    text = parse_power_matrix(html)
    
    # Print a portion of the text to understand structure
    print("\n" + "="*60)
    print("Sample of page text:")
    print("="*60)
    print(text[:3000])
    
    print("\n" + "="*60)
    print("Trying detailed records page...")
    detail_html = get_detailed_records_page()
    if detail_html:
        with open('power_matrix_detail.html', 'w') as f:
            f.write(detail_html)
        print("Saved detailed page to power_matrix_detail.html")
        
        soup = BeautifulSoup(detail_html, 'html.parser')
        detail_text = soup.get_text()
        print("\nSample of detailed page:")
        print(detail_text[:3000])


if __name__ == "__main__":
    main()

