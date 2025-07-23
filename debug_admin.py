#!/usr/bin/env python3
# Debug script to check admin ID parsing

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get the values
token = os.getenv("BOT_TOKEN")
admin_ids_raw = os.getenv("ADMIN_IDS", "")

print("=== DEBUG INFO ===")
print(f"BOT_TOKEN exists: {bool(token)}")
print(f"ADMIN_IDS raw: '{admin_ids_raw}'")
print(f"ADMIN_IDS type: {type(admin_ids_raw)}")

# Parse admin IDs (same logic as in your bot)
admin_ids = [int(id) for id in admin_ids_raw.split(",") if id]
print(f"Parsed ADMIN_IDS: {admin_ids}")
print(f"Parsed ADMIN_IDS types: {[type(id) for id in admin_ids]}")

# Test your user ID
your_user_id = 5188628785  # Replace with your actual full ID
print(f"Your user ID: {your_user_id}")
print(f"Your user ID type: {type(your_user_id)}")
print(f"Is admin check: {your_user_id in admin_ids}")

# Test the is_admin function
def is_admin(user_id: int) -> bool:
    return user_id in admin_ids

print(f"is_admin({your_user_id}): {is_admin(your_user_id)}")

# Additional debugging
print("\n=== DETAILED COMPARISON ===")
for i, admin_id in enumerate(admin_ids):
    print(f"Admin ID {i}: {admin_id} == {your_user_id} ? {admin_id == your_user_id}")