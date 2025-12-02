#!/usr/bin/env python3
"""
Test script to verify access to the Dougin FFL website.
"""

import requests
from bs4 import BeautifulSoup

# Configuration
BASE_URL = "https://www.dougin.com/ffl"
LEAGUE_URL = f"{BASE_URL}/ffl.cfm?League=3"

# Credentials
TEAM_NAME = "Boomie's Boys"  # or "Karma Chameleons" for other league
PASSWORD = "Loser"

def test_access():
    """Test basic access to the FFL website."""
    session = requests.Session()
    
    print("=" * 60)
    print("Testing access to Dougin FFL Website")
    print("=" * 60)
    
    # First, try to access the main page without login
    print("\n1. Testing basic page access...")
    try:
        response = session.get(LEAGUE_URL, timeout=10)
        print(f"   Status Code: {response.status_code}")
        print(f"   Content Length: {len(response.text)} bytes")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.find('title')
        print(f"   Page Title: {title.text if title else 'No title found'}")
        
    except requests.exceptions.RequestException as e:
        print(f"   Error accessing page: {e}")
        return False
    
    # Look for login form
    print("\n2. Looking for login mechanism...")
    forms = soup.find_all('form')
    print(f"   Found {len(forms)} form(s)")
    
    for i, form in enumerate(forms):
        action = form.get('action', 'No action')
        method = form.get('method', 'No method')
        print(f"   Form {i+1}: action='{action}', method='{method}'")
        
        inputs = form.find_all('input')
        for inp in inputs:
            inp_name = inp.get('name', 'unnamed')
            inp_type = inp.get('type', 'text')
            print(f"      - Input: name='{inp_name}', type='{inp_type}'")
    
    # Look for any links that might indicate login
    print("\n3. Looking for login links...")
    links = soup.find_all('a')
    login_links = [a for a in links if 'login' in str(a).lower()]
    for link in login_links[:5]:
        href = link.get('href', 'no href')
        text = link.text.strip()
        print(f"   Login link: '{text}' -> {href}")
    
    # Try to find team-related content
    print("\n4. Looking for team information...")
    team_refs = soup.find_all(string=lambda text: text and "boomie" in text.lower())
    for ref in team_refs[:5]:
        print(f"   Found reference: {ref.strip()[:80]}...")
    
    # Check for standings or schedule links
    print("\n5. Looking for key data links...")
    key_terms = ['standings', 'schedule', 'roster', 'scores', 'matchup']
    for term in key_terms:
        term_links = [a for a in links if term in str(a).lower()]
        if term_links:
            for link in term_links[:2]:
                href = link.get('href', 'no href')
                text = link.text.strip()
                print(f"   {term.title()}: '{text}' -> {href}")
    
    # Try to access the login page directly
    print("\n6. Attempting to find and access login page...")
    login_page_candidates = [
        f"{BASE_URL}/login.cfm",
        f"{BASE_URL}/login.cfm?League=3",
        f"{BASE_URL}/ffl.cfm?action=login&League=3",
    ]
    
    for login_url in login_page_candidates:
        try:
            resp = session.get(login_url, timeout=10)
            if resp.status_code == 200 and len(resp.text) > 500:
                print(f"   Found potential login page: {login_url}")
                login_soup = BeautifulSoup(resp.text, 'html.parser')
                login_forms = login_soup.find_all('form')
                if login_forms:
                    print(f"   Contains {len(login_forms)} form(s)")
        except:
            pass
    
    # Try to POST login credentials
    print("\n7. Attempting login with credentials...")
    
    # Common login form field names
    login_attempts = [
        {
            'url': f"{BASE_URL}/ffl.cfm?League=3",
            'data': {'team': TEAM_NAME, 'password': PASSWORD}
        },
        {
            'url': f"{BASE_URL}/ffl.cfm?League=3",
            'data': {'teamname': TEAM_NAME, 'password': PASSWORD}
        },
        {
            'url': f"{BASE_URL}/ffl.cfm?League=3",
            'data': {'Team': TEAM_NAME, 'Password': PASSWORD}
        },
        {
            'url': f"{BASE_URL}/login.cfm?League=3",
            'data': {'team': TEAM_NAME, 'password': PASSWORD}
        },
    ]
    
    for attempt in login_attempts:
        try:
            resp = session.post(attempt['url'], data=attempt['data'], timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Check if we're now logged in (look for logout link or team name in welcome message)
            page_text = soup.get_text().lower()
            if 'logout' in page_text or 'welcome' in page_text:
                print(f"   Possible successful login with: {attempt['data']}")
                print(f"   Checking for authenticated content...")
                
                # Look for team-specific content
                if 'boomie' in page_text:
                    print("   ✓ Found team reference - appears to be logged in!")
                    return True
        except Exception as e:
            print(f"   Login attempt failed: {e}")
    
    print("\n" + "=" * 60)
    print("Summary: Basic access successful, login mechanism needs investigation")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    test_access()

