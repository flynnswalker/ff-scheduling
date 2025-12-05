#!/usr/bin/env python3
print("Starting import test...")

print("1. Importing json...")
import json

print("2. Importing copy...")
import copy

print("3. Importing defaultdict...")
from collections import defaultdict

print("4. About to import app functions...")

# Import one at a time
print("4a. Importing get_team_division...")
from app import get_team_division

print("4b. Importing calculate_win_pct...")
from app import calculate_win_pct

print("4c. Importing get_h2h_record...")
from app import get_h2h_record

print("4d. Importing get_lowest_in_division_for_relegation...")
from app import get_lowest_in_division_for_relegation

print("4e. Importing compare_cross_division_for_relegation...")
from app import compare_cross_division_for_relegation

print("4f. Importing determine_playoff_teams...")
from app import determine_playoff_teams

print("4g. Importing determine_relegation_teams...")
from app import determine_relegation_teams

print("All imports successful!")

