#!/usr/bin/env python3
"""
Explore the Dougin FFL website structure to find data needed for playoff scenario analysis.
"""

import requests
from bs4 import BeautifulSoup
import re

# Configuration
BASE_URL = "https://www.dougin.com/ffl"
LEAGUE_URL = f"{BASE_URL}/ffl.cfm?League=3"

# Credentials
TEAM_NAME = "Boomie's Boys"
PASSWORD = "Loser"

# Use a browser-like User-Agent
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
}

def create_session():
    """Create an authenticated session."""
    session = requests.Session()
    session.headers.update(HEADERS)
    
    # First, get the login page to establish session
    print("Establishing session...")
    login_page_url = f"{BASE_URL}/FFL.cfm?FID=Login.cfm&League=3"
    resp = session.get(login_page_url, timeout=10)
    print(f"  Login page: {resp.status_code}")
    
    # Parse login form to find actual form fields
    soup = BeautifulSoup(resp.text, 'html.parser')
    forms = soup.find_all('form')
    print(f"  Forms found: {len(forms)}")
    
    for form in forms:
        inputs = form.find_all('input')
        for inp in inputs:
            print(f"    Input: name='{inp.get('name')}', type='{inp.get('type')}'")
    
    # Try to login
    print("\nAttempting login...")
    login_data = {
        'Team': TEAM_NAME,
        'Password': PASSWORD,
        'League': '3'
    }
    
    # Post to the login form
    resp = session.post(login_page_url, data=login_data, timeout=10)
    print(f"  Login POST: {resp.status_code}")
    
    # Check if logged in
    soup = BeautifulSoup(resp.text, 'html.parser')
    page_text = soup.get_text().lower()
    
    if 'logout' in page_text or 'boomie' in page_text:
        print("  ✓ Login appears successful!")
    else:
        print("  ? Login status uncertain")
        # Try alternate login method
        login_data2 = {
            'team': TEAM_NAME,
            'password': PASSWORD,
        }
        resp = session.post(LEAGUE_URL, data=login_data2, timeout=10)
        print(f"  Alternate login: {resp.status_code}")
    
    return session

def explore_page(session, url, description, show_full=False):
    """Fetch and analyze a page."""
    print(f"\n{'='*60}")
    print(f"Exploring: {description}")
    print(f"URL: {url}")
    print('='*60)
    
    try:
        resp = session.get(url, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        print(f"Status: {resp.status_code}, Length: {len(resp.text)} bytes")
        
        # Check for errors
        if 'Error Occurred' in resp.text:
            print("⚠ Page contains error messages")
            return None
        
        # Get title
        title = soup.find('title')
        if title:
            print(f"Title: {title.text.strip()}")
        
        # Find tables (most league data is in tables)
        tables = soup.find_all('table')
        print(f"Tables found: {len(tables)}")
        
        if show_full:
            print("\nFull page text preview:")
            print("-" * 40)
            text = soup.get_text()
            # Clean up whitespace
            text = re.sub(r'\n+', '\n', text)
            text = re.sub(r' +', ' ', text)
            print(text[:3000])
        
        return soup
        
    except Exception as e:
        print(f"Error: {e}")
        return None

def explore_all_links(session):
    """Get all links from the main page."""
    print("\n" + "#"*60)
    print("# ALL AVAILABLE LINKS FROM MAIN PAGE")
    print("#"*60)
    
    resp = session.get(LEAGUE_URL, timeout=10)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    links = soup.find_all('a')
    seen = set()
    
    for link in links:
        href = link.get('href', '')
        text = link.get_text(strip=True)
        
        if href and text and href not in seen and not href.startswith('#'):
            seen.add(href)
            print(f"  {text[:35]:35} -> {href[:60]}")

def get_power_matrix(session):
    """Get the Power Matrix which contains standings."""
    print("\n" + "#"*60)
    print("# POWER MATRIX (STANDINGS)")
    print("#"*60)
    
    url = f"{BASE_URL}/FFL.cfm?Matrix=1&League=3"
    soup = explore_page(session, url, "Power Matrix", show_full=True)
    
    if soup:
        # Also try with explicit league parameter
        url2 = f"{BASE_URL}/ffl.cfm?Matrix=1&League=3"
        resp = session.get(url2, timeout=10)
        if 'Error' not in resp.text:
            print("\n\nAlternate URL worked!")
            soup = BeautifulSoup(resp.text, 'html.parser')
            text = soup.get_text()
            text = re.sub(r'\n+', '\n', text)
            text = re.sub(r' +', ' ', text)
            print(text[:3000])

def get_league_schedule(session):
    """Get the full league schedule."""
    print("\n" + "#"*60)
    print("# LEAGUE SCHEDULE")
    print("#"*60)
    
    url = f"{BASE_URL}/FFL.cfm?FID=LeagueSchedule.cfm&League=3"
    soup = explore_page(session, url, "League Schedule", show_full=True)

def get_team_rosters(session):
    """Get team roster info."""
    print("\n" + "#"*60)
    print("# TEAM ROSTERS")
    print("#"*60)
    
    url = f"{BASE_URL}/LeagueRoster.cfm?League=3"
    soup = explore_page(session, url, "Team Rosters", show_full=True)

def get_home_page_content(session):
    """Get the main home page content including recent standings."""
    print("\n" + "#"*60)
    print("# HOME PAGE CONTENT")
    print("#"*60)
    
    resp = session.get(LEAGUE_URL, timeout=10)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    print(f"Status: {resp.status_code}")
    
    # Get all text content
    text = soup.get_text()
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r' +', ' ', text)
    
    print("\nPage content:")
    print("-" * 40)
    print(text[:4000])
    
    # Look for team links specifically
    print("\n\nTeam Links:")
    print("-" * 40)
    for link in soup.find_all('a'):
        href = link.get('href', '')
        text = link.get_text(strip=True)
        if any(team in text.lower() for team in ['boomie', 'hampden', 'mobius', 'direction', 'gorilla', 'pollos', 'rebig', 'ytterby', 'shore', 'nip', 'lester', 'original', 'sith']):
            print(f"  {text} -> {href}")

def main():
    print("="*60)
    print("DOUGIN FFL LEAGUE EXPLORER")
    print("="*60)
    
    session = create_session()
    
    # Get home page content first
    get_home_page_content(session)
    
    # Explore all available links
    explore_all_links(session)
    
    # Get Power Matrix (standings)
    get_power_matrix(session)
    
    # Get schedule
    get_league_schedule(session)

if __name__ == "__main__":
    main()
