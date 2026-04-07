"""
Migration script: SQLite → Neo4j
Part 1: Read data from SQLite
"""

import sqlite3
from typing import List, Dict, Tuple

def read_users_from_sqlite(db_path: str = 'social_network.db') -> List[Dict]:
    """Read all users from SQLite database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, name FROM users')
    users = [{'id': row[0], 'username': row[1], 'name': row[2]} for row in cursor.fetchall()]
    conn.close()
    return users

def read_posts_from_sqlite(db_path: str = 'social_network.db') -> List[Dict]:
    """Read all posts from SQLite database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT id, user_id, content, timestamp FROM posts')
    posts = [{'id': row[0], 'user_id': row[1], 'content': row[2], 'timestamp': row[3]} for row in cursor.fetchall()]
    conn.close()
    return posts

def read_followers_from_sqlite(db_path: str = 'social_network.db') -> List[Tuple]:
    """Read all follower relationships from SQLite database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT follower_id, followee_id FROM followers')
    followers = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    return followers

if __name__ == '__main__':
    print("Reading data from SQLite database...")
    
    users = read_users_from_sqlite()
    posts = read_posts_from_sqlite()
    followers = read_followers_from_sqlite()
    
    print(f"✓ Read {len(users)} users")
    print(f"✓ Read {len(posts)} posts")
    print(f"✓ Read {len(followers)} follower relationships")
    
    print("\nSample users:")
    for user in users[:3]:
        print(f"  {user}")
    
    print("\nSample posts:")
    for post in posts[:3]:
        print(f"  {post}")
    
    print("\nSample follower relationships:")
    for follower in followers[:3]:
        print(f"  {follower}")
