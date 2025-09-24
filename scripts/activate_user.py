#!/usr/bin/env python3
"""
Script to activate a user account for testing purposes
Usage: python scripts/activate_user.py <email>
"""
import asyncio
import sys
import os

# Add backend to path
backend_path = os.path.join(os.path.dirname(__file__), '..', 'backend')
sys.path.insert(0, backend_path)

from app.db.client import connect_to_mongo, close_mongo_connection, mongo_client

async def activate_user(email: str):
    """Activate a user account by email"""
    try:
        await connect_to_mongo()
        
        # Update user status to active
        result = await mongo_client.database.users.update_one(
            {"email": email},
            {"$set": {"status": "active", "email_verified": True}}
        )
        
        if result.modified_count > 0:
            print(f"Successfully activated user: {email}")
        elif result.matched_count > 0:
            print(f"User {email} was already activated")
        else:
            print(f"User not found: {email}")
            
    except Exception as e:
        print(f"Error activating user: {e}")
    finally:
        await close_mongo_connection()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/activate_user.py <email>")
        sys.exit(1)
    
    email = sys.argv[1]
    asyncio.run(activate_user(email))