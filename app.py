from flask import Flask, request, redirect, url_for, render_template, session, flash, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room

import json

import os

from typing import Dict, Optional, Any

from datetime import datetime, timezone

import pytz

import uuid

from werkzeug.utils import secure_filename



app = Flask(__name__)

app.secret_key = 'your_secret_key'  # Set a secret key for session management



# Mock user data with username, email, and password

users = {

    "user@example.com": {"username": "user1", "password": "password123"}

}



VALID_FONT_SIZES = ['small', 'medium', 'large']

VALID_VISIBILITIES = ['public', 'private', 'friends']

VALID_LANGUAGES = ['en', 'es', 'fr']

VALID_TIMEZONES = pytz.all_timezones  # Using all available timezones from pytz



def load_users():

    try:

        with open('users.json', 'r') as f:

            return json.load(f)

    except FileNotFoundError:

        return {}  # Return an empty dictionary if the file doesn't exist yet



def save_users(users):

    with open('users.json', 'w') as f:

        json.dump(users, f, indent=4)



@app.route('/login', methods=['GET', 'POST'])

def login():

    if request.method == 'POST':

        username = request.form['username']

        password = request.form['password']

        

        users = load_users()  # Load users from the JSON file

        user_email = None

        

        # Find the user by username (not email)

        for email, user_info in users.items():

            if user_info['username'] == username and user_info['password'] == password:

                user_email = email

                break

        

        if user_email:

            session['user'] = users[user_email]['username']  # Store username in session

            flash('Login successful!', 'success')

            return redirect(url_for('index'))

        else:

            flash('Invalid credentials. Please try again.', 'danger')

            return redirect(url_for('login'))

    

    return render_template('login.html')





@app.route('/signup', methods=['GET', 'POST'])

def signup():

    if request.method == 'POST':

        username = request.form['username']

        email = request.form['email']

        password = request.form['password']

        

        users = load_users()  # Load users from the JSON file

        

        # Ensure the email and username don't already exist

        if email not in users and all(user['username'] != username for user in users.values()):

            users[email] = {"username": username, "password": password}  # Add new user to the dictionary

            save_users(users)  # Save updated users to the JSON file

            flash('Signup successful! Please login.', 'success')

            return redirect(url_for('login'))

        else:

            flash('Email or username already exists. Please login.', 'danger')

            return redirect(url_for('login'))

    

    return render_template('signup.html')





# Load data

def load_data():

    with open('data.json', 'r') as f:

        return json.load(f)



# Save data

def save_data(data):

    with open('data.json', 'w') as f:

        json.dump(data, f, indent=4)



@app.route('/')

def index():

    data = load_data()

    username = session.get('user')
    

    # Get all user profiles for post authors

    user_profiles = {}

    for post in data['posts']:

        user_profiles[post['author']] = get_user_profile(post['author'])

    

    return render_template('index.html', 

                         posts=data['posts'], 

                         username=username,

                         user_profiles=user_profiles)



@app.route('/get_usernames')

def get_usernames():

    with open('users.json', 'r') as f:

        data = json.load(f)

    usernames = [user_info['username'] for user_info in data.values()]

    return jsonify(usernames)





@app.route('/mypage')

def my_page():

    # Ensure user is logged in

    if 'user' not in session:

        flash('Please login to access your page.', 'danger')

        return redirect(url_for('login'))



    # Get user data

    user_email = session['user']

    data = load_data()

    

    # Filter posts by user

    user_posts = [post for post in data['posts'] if post['author'] == user_email]

    

    # Calculate total upvotes

    total_upvotes = sum(post.get('upvotes', 0) for post in user_posts)

    

    # Get user profile

    user_profile = get_user_profile(user_email)

    

    return render_template('mypage.html', 

                         posts=user_posts,

                         user_profile=user_profile,

                         total_upvotes=total_upvotes)



def get_user_profile(username):

    try:

        with open('user_profiles.json', 'r') as f:

            profiles = json.load(f)

            return profiles.get(username, {

                'username': username,

                'bio': '',

                'email': username,  # Using email as default since that's what we store in session

                'github': ''

            })

    except (FileNotFoundError, json.JSONDecodeError):

        # Return default profile if file doesn't exist or is invalid

        return {

            'username': username,

            'bio': '',

            'email': username,

            'github': ''

        }



def save_user_profile(username, profile_data):

    try:

        # Load existing profiles

        try:

            with open('user_profiles.json', 'r') as f:

                profiles = json.load(f)

        except (FileNotFoundError, json.JSONDecodeError):

            profiles = {}

        

        # Update or add new profile

        profiles[username] = profile_data

        

        # Save back to file

        with open('user_profiles.json', 'w') as f:

            json.dump(profiles, f, indent=4)

            

        return True

    except Exception as e:

        print(f"Error saving profile: {e}")

        return False







def create_comment_id():

    return str(uuid.uuid4())



@app.route('/comment/<int:post_id>', methods=['POST'])

def add_comment(post_id):

    if 'user' not in session:

        return jsonify({"error": "Please login to comment"}), 401

    

    current_user = session['user']

    comment_text = request.form.get('comment')

    

    if not comment_text:

        return jsonify({"error": "Comment cannot be empty"}), 400

    

    data = load_data()

    post = next((p for p in data['posts'] if p['id'] == post_id), None)

    

    if post is None:

        return jsonify({"error": "Post not found"}), 404

    

    new_comment = {

        "id": create_comment_id(),

        "username": current_user,

        "text": comment_text,

        "timestamp": datetime.now(timezone.utc).isoformat(),

        "likes": 0,

        "liked_by": [],

        "replies": []

    }

    

    if 'comments' not in post:

        post['comments'] = []

    

    post['comments'].append(new_comment)

    save_data(data)

    

    # Return the new comment with formatted timestamp

    return jsonify({

        **new_comment,

        "formatted_timestamp": datetime.fromisoformat(new_comment["timestamp"]).strftime("%B %d, %Y %I:%M %p")

    })



@app.route('/comment/<int:post_id>/<comment_id>/reply', methods=['POST'])

def add_reply(post_id, comment_id):

    if 'user' not in session:

        return jsonify({"error": "Please login to reply"}), 401

    

    current_user = session['user']

    reply_text = request.json.get('reply')

    

    if not reply_text:

        return jsonify({"error": "Reply cannot be empty"}), 400

    

    data = load_data()

    post = next((p for p in data['posts'] if p['id'] == post_id), None)

    

    if post is None:

        return jsonify({"error": "Post not found"}), 404

    

    comment = next((c for c in post.get('comments', []) if str(c.get('id')) == str(comment_id)), None)

    if comment is None:

        return jsonify({"error": "Comment not found"}), 404

    

    new_reply = {

        "id": str(uuid.uuid4()),

        "username": current_user,

        "text": reply_text,

        "timestamp": datetime.now(timezone.utc).isoformat(),

        "likes": 0,

        "liked_by": []

    }

    

    if 'replies' not in comment:

        comment['replies'] = []

    

    comment['replies'].append(new_reply)

    save_data(data)

    

    # Return the new reply with formatted timestamp

    return jsonify({

        **new_reply,

        "formatted_timestamp": datetime.fromisoformat(new_reply["timestamp"]).strftime("%B %d, %Y %I:%M %p")

    })



@app.route('/comment/<int:post_id>/<comment_id>/like', methods=['POST'])

def like_comment(post_id, comment_id):

    if 'user' not in session:

        return jsonify({"error": "Please login to like comments"}), 401

    

    current_user = session['user']

    data = load_data()

    

    # Find the post and comment

    post = next((p for p in data['posts'] if p['id'] == post_id), None)

    if not post:

        return jsonify({"error": "Post not found"}), 404

    

    comment = next((c for c in post.get('comments', []) if c['id'] == comment_id), None)

    if not comment:

        return jsonify({"error": "Comment not found"}), 404

    

    # Initialize liked_by if not present

    if 'liked_by' not in comment:

        comment['liked_by'] = []

    if 'likes' not in comment:

        comment['likes'] = 0

    

    # Toggle like status

    if current_user in comment['liked_by']:

        comment['liked_by'].remove(current_user)

        comment['likes'] = max(0, comment['likes'] - 1)

        is_liked = False

    else:

        comment['liked_by'].append(current_user)

        comment['likes'] += 1

        is_liked = True

    

    save_data(data)

    

    return jsonify({

        "likes": comment['likes'],

        "isLiked": is_liked

    })



@app.route('/comment/<int:post_id>/<comment_id>/<reply_id>/like', methods=['POST'])

def like_reply(post_id, comment_id, reply_id):

    if 'user' not in session:

        return jsonify({"error": "Please login to like replies"}), 401

    

    current_user = session['user']

    data = load_data()

    

    # Find the post, comment, and reply

    post = next((p for p in data['posts'] if p['id'] == post_id), None)

    if not post:

        return jsonify({"error": "Post not found"}), 404

    

    comment = next((c for c in post.get('comments', []) if c['id'] == comment_id), None)

    if not comment:

        return jsonify({"error": "Comment not found"}), 404

    

    reply = next((r for r in comment.get('replies', []) if r['id'] == reply_id), None)

    if not reply:

        return jsonify({"error": "Reply not found"}), 404

    

    # Initialize liked_by if not present

    if 'liked_by' not in reply:

        reply['liked_by'] = []

    if 'likes' not in reply:

        reply['likes'] = 0

    

    # Toggle like status

    if current_user in reply['liked_by']:

        reply['liked_by'].remove(current_user)

        reply['likes'] = max(0, reply['likes'] - 1)

        is_liked = False

    else:

        reply['liked_by'].append(current_user)

        reply['likes'] += 1

        is_liked = True

    

    save_data(data)

    

    return jsonify({

        "likes": reply['likes'],

        "isLiked": is_liked

    })



@app.route('/search', methods=['GET'])

def search():

    query = request.args.get('query', '')

    data = load_data()

    # Simple search by title or description

    filtered_posts = [post for post in data['posts'] if query.lower() in post['title'].lower() or query.lower() in post['description'].lower()]

    return render_template('index.html', posts=filtered_posts)



@app.route('/logout', methods=['GET', 'POST'])

def logout():

    if request.method == 'POST':

        session.pop('user', None)

        flash('You have been logged out.', 'success')

        return redirect(url_for('login'))

    return redirect(url_for('index'))



# Load data

def load_data():

    with open('data.json', 'r') as f:

        return json.load(f)



# Save data

def save_data(data):

    with open('data.json', 'w') as f:

        json.dump(data, f, indent=4)



def load_user_votes():

    try:

        with open('user_votes.json', 'r') as f:

            return json.load(f)

    except FileNotFoundError:

        return {}



def save_user_votes(votes):

    with open('user_votes.json', 'w') as f:

        json.dump(votes, f, indent=4)



@app.route('/upvote/<int:post_id>', methods=['POST'])

def upvote(post_id):

    if 'user' not in session:

        return jsonify({"error": "Please login to vote"}), 401

    

    current_user = session['user']

    data = load_data()

    user_votes = load_user_votes()

    

    # Initialize user's votes if not present

    if current_user not in user_votes:

        user_votes[current_user] = {}

    

    # Find the post

    post = next((p for p in data['posts'] if p['id'] == post_id), None)

    if post is None:

        return jsonify({"error": "Post not found"}), 404

    

    # Initialize vote counts if not present

    post.setdefault('upvotes', 0)

    post.setdefault('downvotes', 0)

    

    post_votes = user_votes[current_user].get(str(post_id))

    

    if post_votes == "upvote":

        # Remove upvote

        post['upvotes'] = max(0, post['upvotes'] - 1)

        user_votes[current_user][str(post_id)] = None

    elif post_votes == "downvote":

        # Change from downvote to upvote

        post['downvotes'] = max(0, post['downvotes'] - 1)

        post['upvotes'] += 1

        user_votes[current_user][str(post_id)] = "upvote"

    else:

        # New upvote

        post['upvotes'] += 1

        user_votes[current_user][str(post_id)] = "upvote"

    

    save_data(data)

    save_user_votes(user_votes)

    

    return jsonify({

        "upvotes": post['upvotes'],

        "downvotes": post['downvotes'],

        "userVote": user_votes[current_user].get(str(post_id))

    })





@app.route('/downvote/<int:post_id>', methods=['POST'])

def downvote(post_id):

    if 'user' not in session:

        return jsonify({"error": "Please login to vote"}), 401

    

    current_user = session['user']

    data = load_data()

    user_votes = load_user_votes()

    

    # Initialize user's votes if not present

    if current_user not in user_votes:

        user_votes[current_user] = {}

    

    # Find the post

    post = next((p for p in data['posts'] if p['id'] == post_id), None)

    if post is None:

        return jsonify({"error": "Post not found"}), 404

    

    # Initialize vote counts if not present

    post.setdefault('upvotes', 0)

    post.setdefault('downvotes', 0)

    

    post_votes = user_votes[current_user].get(str(post_id))

    

    if post_votes == "downvote":

        # Remove downvote

        post['downvotes'] = max(0, post['downvotes'] - 1)

        user_votes[current_user][str(post_id)] = None

    elif post_votes == "upvote":

        # Change from upvote to downvote

        post['upvotes'] = max(0, post['upvotes'] - 1)

        post['downvotes'] += 1

        user_votes[current_user][str(post_id)] = "downvote"

    else:

        # New downvote

        post['downvotes'] += 1

        user_votes[current_user][str(post_id)] = "downvote"

    

    save_data(data)

    save_user_votes(user_votes)

    

    return jsonify({

        "upvotes": post['upvotes'],

        "downvotes": post['downvotes'],

        "userVote": user_votes[current_user].get(str(post_id))

    })





@app.route('/get_vote_status/<int:post_id>', methods=['GET'])

def get_vote_status(post_id):

    if 'user' not in session:

        return jsonify({"error": "Not logged in"}), 401

    

    current_user = session['user']

    user_votes = load_user_votes()

    

    if current_user not in user_votes:

        return jsonify({"vote": None})

    

    return jsonify({

        "vote": user_votes[current_user].get(str(post_id))

    })





@app.route('/create_post', methods=['GET', 'POST'])

def create_post():

    if 'user' not in session:

        flash('Please login to create a post.', 'danger')

        return redirect(url_for('login'))



    if request.method == 'POST':

        title = request.form['title']

        description = request.form['description']

        link = request.form['link']

        

        # Generate new post data

        new_post = {

            "id": len(load_data()["posts"]) + 1,  # Auto-incrementing ID

            "title": title,

            "description": description,

            "link": link,

            "upvotes": 0,

            "downvotes": 0,

            "comments": [],

            "author": session['user']

        }

        

        # Load existing posts and append the new post

        data = load_data()

        data["posts"].append(new_post)

        save_data(data)

        

        flash('Post created successfully!', 'success')

        return redirect(url_for('my_page'))



    return render_template('create_post.html')



@app.route('/post/<int:post_id>')

def post(post_id):

    data = load_data()

    post = next((p for p in data['posts'] if p['id'] == post_id), None)

    if not post:

        return redirect(url_for('index'))
    

    # Get all user profiles for the post author and commenters

    user_profiles = {}

    user_profiles[post['author']] = get_user_profile(post['author'])
    

    for comment in post['comments']:

        user_profiles[comment['username']] = get_user_profile(comment['username'])

        for reply in comment.get('replies', []):

            user_profiles[reply['username']] = get_user_profile(reply['username'])

    

    return render_template('post.html', 

                         post=post, 

                         current_user=session.get('user'),

                         user_profiles=user_profiles)



def load_user_settings():

    try:

        with open('user_settings.json', 'r') as f:

            return json.load(f)

    except FileNotFoundError:

        return {}



def save_user_settings(settings: Dict[str, Any]):

    with open('user_settings.json', 'w') as f:

        json.dump(settings, f, indent=4)



def get_user_settings(username: str) -> Dict[str, Any]:

    settings = load_user_settings()

    if username not in settings:

        # Default settings

        settings[username] = {

            'fontSize': 'medium',

            'emailNotifications': True,

            'commentNotifications': True,

            'profileVisibility': 'public',

            'activityStatus': True,

            'language': 'en',

            'timezone': 'UTC',

            'theme': 'light'

        }

        save_user_settings(settings)

    return settings[username]



@app.route('/settings')

def settings():

    if 'user' not in session:

        return redirect(url_for('login'))

    

    username = session['user']

    user_settings = get_user_settings(username)

    

    return render_template('settings.html', 

                         settings=user_settings,

                         timezones=VALID_TIMEZONES,

                         languages=VALID_LANGUAGES)



@app.route('/save_settings', methods=['POST'])

def save_settings():

    if 'user' not in session:

        return jsonify({'error': 'Not logged in'}), 401

    

    username = session['user']

    data = request.get_json()

    

    # Validate and sanitize settings

    new_settings = {

        'fontSize': data.get('fontSize') if data.get('fontSize') in VALID_FONT_SIZES else 'medium',

        'emailNotifications': bool(data.get('emailNotifications')),

        'commentNotifications': bool(data.get('commentNotifications')),

        'profileVisibility': data.get('profileVisibility') if data.get('profileVisibility') in VALID_VISIBILITIES else 'public',

        'activityStatus': bool(data.get('activityStatus')),

        'language': data.get('language') if data.get('language') in VALID_LANGUAGES else 'en',

        'timezone': data.get('timezone') if data.get('timezone') in VALID_TIMEZONES else 'UTC',

        'theme': data.get('theme', 'light')

    }

    

    # Load current settings

    all_settings = load_user_settings()

    

    # Update user's settings

    all_settings[username] = new_settings

    

    # Save to file

    save_user_settings(all_settings)

    

    return jsonify({'message': 'Settings saved successfully'})



@app.route('/delete_account', methods=['POST'])

def delete_account():

    if 'user' not in session:

        return jsonify({'error': 'Not logged in'}), 401

    

    username = session['user']

    

    try:

        # Load users data

        with open('users.json', 'r') as f:

            users = json.load(f)

        

        # Find and remove user

        user_email = None

        for email, user_info in users.items():

            if user_info['username'] == username:

                user_email = email

                break

        

        if user_email:

            del users[user_email]
            

            # Save updated users

            with open('users.json', 'w') as f:

                json.dump(users, f, indent=4)
            

            # Remove user settings

            settings = load_user_settings()

            if username in settings:

                del settings[username]

                save_user_settings(settings)
            

            # Remove user profile

            profiles = {}

            try:

                with open('user_profiles.json', 'r') as f:

                    profiles = json.load(f)

                if username in profiles:

                    del profiles[username]

                    with open('user_profiles.json', 'w') as f:

                        json.dump(profiles, f, indent=4)

            except FileNotFoundError:

                pass
            

            # Clear session

            session.clear()

            

            return jsonify({'message': 'Account deleted successfully'})

        else:

            return jsonify({'error': 'User not found'}), 404

            

    except Exception as e:

        return jsonify({'error': str(e)}), 500



# Directory where chat files will be stored

CHAT_DIR = 'chats/'



if not os.path.exists(CHAT_DIR):

    os.makedirs(CHAT_DIR)



import json



@app.route('/chat')

def chat():

    if 'user' not in session:

        return redirect(url_for('login'))

    

    current_user = session.get('user')

    existing_chats = []

    user_profiles = {}



    # List all chat files involving the current user

    for filename in os.listdir(CHAT_DIR):

        if filename.endswith(".json") and not filename.endswith("_pinned.json"):

            users = filename[:-5].split("_")

            if current_user in users:

                other_user = users[0] if users[1] == current_user else users[1]

                existing_chats.append(other_user)

                # Get profile for each chat user

                user_profiles[other_user] = get_user_profile(other_user)



    # Load all usernames from users.json

    with open('users.json', 'r') as file:

        users_data = json.load(file)

        all_users = [

            {

                'username': user_info['username'],

                'email': email,

                'profile_pic': get_user_profile(user_info['username']).get('profile_pic')

            }

            for email, user_info in users_data.items() 

            if user_info['username'] != current_user

        ]



    return render_template('chat.html', 

                         existing_chats=existing_chats, 

                         all_users=all_users,

                         user_profiles=user_profiles)







@app.route('/chat/messages/<user>')

def get_messages(user):

    if 'user' not in session:

        return jsonify({'error': 'Not logged in'}), 401

    

    current_user = session.get('user')

    chat_file = get_chat_file(current_user, user)

    

    try:

        if os.path.exists(chat_file):

            with open(chat_file, 'r') as file:

                chat_data = json.load(file)

                return jsonify({

                    'messages': chat_data.get('messages', []),

                    'participants': chat_data.get('participants', [])

                })

    except Exception as e:

        app.logger.error(f"Error reading chat: {str(e)}")

    

    return jsonify({

        'messages': [],

        'participants': [current_user, user]

    })



@app.route('/chat/send/<user>', methods=['POST'])

def send_message(user):

    if 'user' not in session:

        return jsonify({'error': 'Not logged in'}), 401

    

    current_user = session.get('user')

    message_text = request.json.get('message', '').strip()

    

    if not message_text:

        return jsonify({'error': 'Message cannot be empty'}), 400

    

    chat_file = get_chat_file(current_user, user)

    

    try:

        if os.path.exists(chat_file):

            with open(chat_file, 'r') as file:

                chat_data = json.load(file)

        else:

            chat_data = {

                'participants': [current_user, user],

                'messages': []

            }

        

        new_message = {

            'id': str(uuid.uuid4()),

            'sender': current_user,

            'text': message_text,

            'timestamp': datetime.now(timezone.utc).isoformat(),

            'read': False

        }

        

        chat_data['messages'].append(new_message)

        

        with open(chat_file, 'w') as file:

            json.dump(chat_data, file, indent=4)

        

        return jsonify(new_message)

    except Exception as e:

        app.logger.error(f"Error sending message: {str(e)}")

        return jsonify({'error': 'Failed to send message'}), 500



def get_chat_file(user1, user2):

    users = sorted([user1, user2])

    return os.path.join(CHAT_DIR, f"{users[0]}_{users[1]}.json")



@app.route('/chat/pin/<user>', methods=['POST'])

def pin_chat(user):

    if 'user' not in session:

        return jsonify({'error': 'User not logged in'}), 403

    

    # Load or create pinned chats file for the current user

    pinned_file = os.path.join(CHAT_DIR, f"{session['user']}_pinned.json")

    if os.path.exists(pinned_file):

        with open(pinned_file, 'r') as file:

            pinned_chats = json.load(file)

    else:

        pinned_chats = []

    

    # Toggle pin status

    if user in pinned_chats:

        pinned_chats.remove(user)

        is_pinned = False

    else:

        pinned_chats.append(user)

        is_pinned = True

    

    # Save updated pinned chats

    with open(pinned_file, 'w') as file:

        json.dump(pinned_chats, file)

    

    return jsonify({'status': 'success', 'isPinned': is_pinned})



@app.route('/chat/search/<user>', methods=['POST'])

def search_messages(user):

    if 'user' not in session:

        return jsonify({'error': 'User not logged in'}), 403

    

    query = request.json.get('query', '').lower()

    chat_file = get_chat_file(session['user'], user)

    

    if os.path.exists(chat_file):

        with open(chat_file, 'r') as file:

            messages = json.load(file)

            # Filter messages containing the search query

            matching_messages = [

                msg for msg in messages 

                if query in msg['text'].lower()

            ]

        return jsonify({'messages': matching_messages})

    

    return jsonify({'messages': []})



@app.route('/get_available_users')

def get_available_users():

    if 'user' not in session:

        return jsonify({'error': 'Not logged in'}), 401

    

    current_user = session['user']

    

    try:

        with open('users.json', 'r') as f:

            users_data = json.load(f)

            

        # Format users data and exclude current user

        available_users = [

            {

                'username': user_info['username'],

                'email': email,

                'profile_pic': get_user_profile(user_info['username']).get('profile_pic')

            }

            for email, user_info in users_data.items()

            if user_info['username'] != current_user

        ]

        

        return jsonify(available_users)

    except Exception as e:

        app.logger.error(f"Error loading users: {str(e)}")

        return jsonify({'error': 'Failed to load users'}), 500



@app.route('/update_legacy_comments', methods=['POST'])

def update_legacy_comments():

    if 'user' not in session:

        return jsonify({"error": "Not authorized"}), 401

    

    data = load_data()

    

    for post in data['posts']:

        updated_comments = []

        for comment in post.get('comments', []):

            # Check if comment needs updating

            if 'id' not in comment:

                updated_comment = {

                    "id": str(uuid.uuid4()),

                    "username": comment.get('username', 'anonymous'),

                    "text": comment.get('text', ''),

                    "timestamp": comment.get('timestamp', datetime.now(timezone.utc).isoformat()),

                    "likes": comment.get('likes', 0),

                    "liked_by": comment.get('liked_by', []),

                    "replies": []

                }

                # Move any existing replies to new format

                for reply in comment.get('replies', []):

                    if isinstance(reply, dict) and 'id' not in reply:

                        reply['id'] = str(uuid.uuid4())

                        reply['timestamp'] = reply.get('timestamp', datetime.now(timezone.utc).isoformat())

                        reply['likes'] = reply.get('likes', 0)

                        reply['liked_by'] = reply.get('liked_by', [])

                updated_comment['replies'] = comment.get('replies', [])

                updated_comments.append(updated_comment)

            else:

                updated_comments.append(comment)

        post['comments'] = updated_comments

    

    save_data(data)

    return jsonify({"message": "Legacy comments updated successfully"})



@app.route('/edit-profile')

def edit_profile():

    if 'user' not in session:

        return redirect(url_for('login'))

    

    # Get user profile from database/file

    user_profile = get_user_profile(session['user'])

    return render_template('edit_profile.html', user_profile=user_profile)



@app.route('/save-profile', methods=['POST'])

def save_profile():

    if 'user' not in session:

        return redirect(url_for('login'))

    

    # Initialize profile data with form fields

    profile_data = {

        'username': session['user'],

        'bio': request.form.get('bio'),

        'email': request.form.get('email'),

        'github': request.form.get('github')

    }

    

    # Handle profile picture upload

    if 'profile_pic' in request.files:

        file = request.files['profile_pic']

        if file and file.filename and allowed_file(file.filename):

            # Get current profile to check if we need to delete old picture

            current_profile = get_user_profile(session['user'])

            if current_profile.get('profile_pic'):

                old_pic_path = os.path.join(app.config['UPLOAD_FOLDER'], current_profile['profile_pic'])

                if os.path.exists(old_pic_path):

                    os.remove(old_pic_path)

            

            # Save new picture

            filename = secure_filename(f"{session['user']}_{file.filename}")

            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            file.save(file_path)

            profile_data['profile_pic'] = filename

        

    # Save profile data

    save_user_profile(session['user'], profile_data)

    flash('Profile updated successfully!', 'success')

    return redirect(url_for('my_page'))



# Add this route for the developer page
@app.route('/developer')
def developer():
    return render_template('developer.html')



# Main entry point

if __name__ == '__main__':

    app.run(debug=True)




