# social_network.py
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import sqlite3
import datetime
from dataclasses import dataclass
from typing import List, Optional

# ======================
# Database Access Layer
# ======================
from neo4j import GraphDatabase

class Database:
    def __init__(self, uri='neo4j://localhost:7687', user='neo4j', password='password'):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self._init_db()

    def _init_db(self):
        with self.driver.session() as session:
            session.execute_write(lambda tx: tx.run(
                "CREATE CONSTRAINT unique_user_id IF NOT EXISTS "
                "FOR (u:User) REQUIRE u.id IS UNIQUE"
            ))
            session.execute_write(lambda tx: tx.run(
                "CREATE CONSTRAINT unique_username IF NOT EXISTS "
                "FOR (u:User) REQUIRE u.username IS UNIQUE"
            ))
            session.execute_write(lambda tx: tx.run(
                "CREATE CONSTRAINT unique_post_id IF NOT EXISTS "
                "FOR (p:Post) REQUIRE p.id IS UNIQUE"
            ))
    
    def _get_connection(self):
        return sqlite3.connect(self.db_name)
    
    # User operations
    def create_user(self, username: str, name: str) -> int:
        with self.driver.session() as session:
            # Get next id
            result = session.execute_read(lambda tx: tx.run("MATCH (u:User) RETURN u.id ORDER BY u.id DESC LIMIT 1").single())
            next_id = (result[0] + 1) if result else 1
            session.execute_write(lambda tx: tx.run(
                "CREATE (u:User {id: $id, username: $username, name: $name})",
                id=next_id, username=username, name=name
            ))
            return next_id
    
    def get_user(self, user_id: int) -> Optional[dict]:
        with self.driver.session() as session:
            result = session.execute_read(lambda tx: tx.run(
                "MATCH (u:User {id: $user_id}) RETURN u.id, u.username, u.name",
                user_id=user_id
            ).single())
            return {'id': result[0], 'username': result[1], 'name': result[2]} if result else None
    
    def get_all_users(self) -> List[dict]:
        with self.driver.session() as session:
            results = session.execute_read(lambda tx: tx.run("MATCH (u:User) RETURN u.id, u.username, u.name"))
            return [{'id': record[0], 'username': record[1], 'name': record[2]} for record in results]
    
    # Post operations
    def create_post(self, user_id: int, content: str) -> int:
        with self.driver.session() as session:
            # Get next post id
            result = session.execute_read(lambda tx: tx.run("MATCH (p:Post) RETURN p.id ORDER BY p.id DESC LIMIT 1").single())
            next_id = (result[0] + 1) if result else 1
            timestamp = datetime.datetime.now()
            session.execute_write(lambda tx: tx.run(
                "MATCH (u:User {id: $user_id}) "
                "CREATE (u)-[:POSTED]->(p:Post {id: $id, content: $content, timestamp: $timestamp})",
                user_id=user_id, id=next_id, content=content, timestamp=timestamp
            ))
            return next_id
    
    def get_posts_by_user(self, user_id: int) -> List[dict]:
        with self.driver.session() as session:
            results = session.execute_read(lambda tx: tx.run(
                "MATCH (u:User {id: $user_id})-[:POSTED]->(p:Post) "
                "RETURN p.id, p.content, p.timestamp, u.username, u.name "
                "ORDER BY p.timestamp DESC",
                user_id=user_id
            ))
            return [{
                'id': record[0],
                'content': record[1],
                'timestamp': record[2],
                'username': record[3],
                'name': record[4]
            } for record in results]
    
    def get_feed(self, user_id: int) -> List[dict]:
        with self.driver.session() as session:
            results = session.execute_read(lambda tx: tx.run(
                "MATCH (u:User {id: $user_id})-[:FOLLOWS]->(f:User)-[:POSTED]->(p:Post) "
                "RETURN p.id, p.content, p.timestamp, f.username, f.name "
                "ORDER BY p.timestamp DESC",
                user_id=user_id
            ))
            return [{
                'id': record[0],
                'content': record[1],
                'timestamp': record[2],
                'username': record[3],
                'name': record[4]
            } for record in results]
    
    # Follow operations
    def follow_user(self, follower_id: int, followee_id: int) -> bool:
        with self.driver.session() as session:
            try:
                session.execute_write(lambda tx: tx.run(
                    "MATCH (f:User {id: $follower_id}), (e:User {id: $followee_id}) "
                    "MERGE (f)-[:FOLLOWS]->(e)",
                    follower_id=follower_id, followee_id=followee_id
                ))
                return True
            except Exception:
                return False
    
    def get_followers(self, user_id: int) -> List[dict]:
        with self.driver.session() as session:
            results = session.execute_read(lambda tx: tx.run(
                "MATCH (u:User {id: $user_id})<-[:FOLLOWS]-(f:User) "
                "RETURN f.id, f.username, f.name",
                user_id=user_id
            ))
            return [{'id': record[0], 'username': record[1], 'name': record[2]} for record in results]
    
    def get_following(self, user_id: int) -> List[dict]:
        with self.driver.session() as session:
            results = session.execute_read(lambda tx: tx.run(
                "MATCH (u:User {id: $user_id})-[:FOLLOWS]->(f:User) "
                "RETURN f.id, f.username, f.name",
                user_id=user_id
            ))
            return [{'id': record[0], 'username': record[1], 'name': record[2]} for record in results]

    def unfollow_user(self, follower_id: int, followee_id: int) -> bool:
        with self.driver.session() as session:
            result = session.execute_write(lambda tx: tx.run(
                "MATCH (f:User {id: $follower_id})-[r:FOLLOWS]->(e:User {id: $followee_id}) "
                "DELETE r",
                follower_id=follower_id, followee_id=followee_id
            ))
            return result.consume().counters.relationships_deleted > 0

# ======================
# Web Application
# ======================
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
db = Database()

# Sample data initialization
with app.app_context():
    # Create some sample users if they don't exist
    if not db.get_all_users():
        db.create_user('alice', 'Alice Smith')
        db.create_user('bob', 'Bob Johnson')
        db.create_user('charlie', 'Charlie Brown')

# ======================
# API Endpoints
# ======================
@app.route('/api/users', methods=['GET'])
def api_get_users():
    return jsonify(db.get_all_users())

@app.route('/api/users/<int:user_id>', methods=['GET'])
def api_get_user(user_id):
    user = db.get_user(user_id)
    return jsonify(user) if user else ('User not found', 404)

@app.route('/api/users/<int:user_id>/posts', methods=['GET'])
def api_get_user_posts(user_id):
    return jsonify(db.get_posts_by_user(user_id))

@app.route('/api/users/<int:user_id>/feed', methods=['GET'])
def api_get_user_feed(user_id):
    return jsonify(db.get_feed(user_id))

@app.route('/api/users/<int:user_id>/followers', methods=['GET'])
def api_get_user_followers(user_id):
    return jsonify(db.get_followers(user_id))

@app.route('/api/users/<int:user_id>/following', methods=['GET'])
def api_get_user_following(user_id):
    return jsonify(db.get_following(user_id))

@app.route('/api/posts', methods=['POST'])
def api_create_post():
    data = request.get_json()
    post_id = db.create_post(data['user_id'], data['content'])
    return jsonify({'post_id': post_id}), 201

@app.route('/api/follow', methods=['POST'])
def api_follow_user():
    data = request.get_json()
    success = db.follow_user(data['follower_id'], data['followee_id'])
    return jsonify({'success': success}), 201 if success else 200

# ======================
# Frontend Routes
# ======================
@app.route('/')
def home():
    users = db.get_all_users()
    current_user = None
    if 'user_id' in session:
        current_user = db.get_user(session['user_id'])
    return render_template('index.html', users=users, current_user=current_user)

@app.route('/user/<int:user_id>')
def user_profile(user_id):
    user = db.get_user(user_id)
    if not user:
        return "User not found", 404
        
    current_user = None
    is_following = False
    
    if 'user_id' in session:
        current_user = db.get_user(session['user_id'])
        if current_user and current_user['id'] != user_id:
            # Check if current user is following this profile user
            following = db.get_following(current_user['id'])
            is_following = any(f['id'] == user_id for f in following)
    
    posts = db.get_posts_by_user(user_id)
    followers = db.get_followers(user_id)
    following = db.get_following(user_id)
    
    return render_template('profile.html', 
                         user=user, 
                         posts=posts,
                         followers=followers,
                         following=following,
                         current_user=current_user,
                         is_following=is_following)

@app.route('/user/<int:user_id>/feed')
def user_feed(user_id):
    user = db.get_user(user_id)
    feed = db.get_feed(user_id)
    return render_template('feed.html', user=user, feed=feed)

@app.route('/create_post', methods=['POST'])
def create_post():
    user_id = int(request.form['user_id'])
    content = request.form['content']
    db.create_post(user_id, content)
    return redirect(url_for('user_profile', user_id=user_id))

@app.route('/login/<int:user_id>')
def login(user_id):
    session['user_id'] = user_id
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('home'))

@app.route('/follow', methods=['POST'])
def follow():
    follower_id = int(request.form['follower_id'])
    followee_id = int(request.form['followee_id'])
    
    # Check if the user is already following
    following = db.get_following(follower_id)
    is_following = any(f['id'] == followee_id for f in following)
    
    if is_following:
        # Implement unfollow functionality (you'll need to add this to your Database class)
        db.unfollow_user(follower_id, followee_id)
    else:
        db.follow_user(follower_id, followee_id)
    
    return redirect(url_for('user_profile', user_id=followee_id))

# ======================
# HTML Templates
# ======================
@app.route('/templates/<template_name>')
def serve_template(template_name):
    return render_template(template_name)

# Template rendering functions
app.jinja_env.globals.update(
    render_index=lambda: render_template('index.html', users=db.get_all_users()),
    render_profile=lambda user_id: render_template(
        'profile.html',
        user=db.get_user(user_id),
        posts=db.get_posts_by_user(user_id),
        followers=db.get_followers(user_id),
        following=db.get_following(user_id)
    )
)

if __name__ == '__main__':
    app.run(debug=True)