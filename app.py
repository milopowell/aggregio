#app.py
#Main Application file for Aggregio
#Handles Strava OAuth2 authentication and basic API interaction

import os
import requests
from flask import Flask, redirect, request, session, render_template_string, url_for
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Set a secret key for session management
app.secret_key = os.getenv('FLASK_SECRET_KEY')

# Strava API credentials
STRAVA_CLIENT_ID = os.getenv('STRAVA_CLIENT_ID')
STRAVA_CLIENT_SECRET = os.getenv('STRAVA_CLIENT_SECRET')

# Strava API URLs
STRAVA_AUTH_URL = 'https://www.strava.com/oauth/authorize'
STRAVA_TOKEN_URL = 'https://www.strava.com/oauth/token'
STRAVA_API_URL = 'https://www.strava.com/api/v3'

# Redirect URI for Strava OAuth
REDIRECT_URI = 'http://127.0.0.1:5000/strava/callback'

#The permissions we want to request from Strava
SCOPE = 'read,activity:read_all'


HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aggregio - Connect Your Fitness Journey</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
        }
        
        .container {
            text-align: center;
            padding: 40px;
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            max-width: 500px;
            width: 90%;
        }
        
        .logo {
            font-size: 3em;
            font-weight: bold;
            margin-bottom: 10px;
            background: linear-gradient(45deg, #fc5200, #ff8c42);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        h1 {
            margin-bottom: 20px;
            font-size: 2.2em;
            font-weight: 300;
        }
        
        p {
            font-size: 1.1em;
            margin-bottom: 30px;
            opacity: 0.9;
            line-height: 1.6;
        }
        
        .connect-btn {
            background: linear-gradient(45deg, #fc5200, #ff8c42);
            color: white;
            padding: 18px 35px;
            text-decoration: none;
            border-radius: 50px;
            font-size: 1.2em;
            font-weight: 600;
            display: inline-block;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(252, 82, 0, 0.3);
        }
        
        .connect-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(252, 82, 0, 0.4);
            background: linear-gradient(45deg, #e04800, #ff7a2a);
        }
        
        .features {
            margin-top: 40px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 20px;
        }
        
        .feature {
            padding: 20px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 15px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .feature-icon {
            font-size: 2em;
            margin-bottom: 10px;
        }
        
        .feature h3 {
            font-size: 1.1em;
            margin-bottom: 8px;
            color: #fc5200;
        }
        
        .feature p {
            font-size: 0.9em;
            margin: 0;
            opacity: 0.8;
        }
        
        @media (max-width: 600px) {
            .container {
                padding: 30px 20px;
            }
            
            .logo {
                font-size: 2.5em;
            }
            
            h1 {
                font-size: 1.8em;
            }
            
            .connect-btn {
                padding: 16px 30px;
                font-size: 1.1em;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">Aggregio</div>
        <h1>Your Fitness Journey Starts Here</h1>
        <p>Connect your Strava account to unlock powerful insights, track your progress, and take your training to the next level.</p>
        
        <a href="{{ auth_url }}" class="connect-btn">🚴 Connect with Strava</a>
        
        <div class="features">
            <div class="feature">
                <div class="feature-icon">📊</div>
                <h3>Analytics</h3>
                <p>Deep insights into your performance</p>
            </div>
            <div class="feature">
                <div class="feature-icon">🎯</div>
                <h3>Goals</h3>
                <p>Track and achieve your targets</p>
            </div>
            <div class="feature">
                <div class="feature-icon">🏆</div>
                <h3>Progress</h3>
                <p>Visualize your improvements</p>
            </div>
        </div>
    </div>
</body>
</html>
"""

#Template for the user's profile page after successful authentication
PROFILE_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aggregio - Profile</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }
        .profile { border: 1px solid #ccc; border-radius: 10px; padding: 20px; display: inline-block; margin: 20px; }
        .profile img { border-radius: 50%; width: 100px; height: 100px; }
        .logout { margin-top: 20px; }
        .logout a { background-color: #fc5200; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; }
        .activities a { background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin: 10px; }
        .error { color: red; margin: 20px; }
    </style>
</head>
<body>
    <div class="profile">
        <h2>Successfully Connected!</h2>
        {% if profile.get('profile_medium') %}
            <img src="{{ profile['profile_medium'] }}" alt="Profile Picture">
        {% elif profile.get('profile') %}
            <img src="{{ profile['profile'] }}" alt="Profile Picture">
        {% else %}
            <div style="width: 100px; height: 100px; background-color: #ccc; border-radius: 50%; display: inline-block; line-height: 100px;">No Image</div>
        {% endif %}
        
        <h3>Welcome, {{ profile.get('firstname', 'User') }} {{ profile.get('lastname', '') }}!</h3>
        <p>Strava ID: {{ profile.get('id', 'Unknown') }}</p>
        <p>Username: {{ profile.get('username', 'N/A') }}</p>
        <p>City: {{ profile.get('city', 'N/A') }}, {{ profile.get('state', 'N/A') }}</p>
        
        <div class="activities">
            <a href="/activities">View Activities</a>
        </div>
    </div>
    <div class="logout">
        <a href="/logout">Logout</a>
    </div>
</body>
</html>
"""

# Template for displaying activities
ACTIVITIES_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aggregio - Activities</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .activity { border: 1px solid #ddd; border-radius: 5px; padding: 15px; margin: 10px 0; }
        .activity h3 { margin-top: 0; color: #fc5200; }
        .back-link { background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; }
        .error { color: red; }
    </style>
</head>
<body>
    <h1>Your Recent Activities</h1>
    <a href="/profile" class="back-link">← Back to Profile</a>
    
    {% if error %}
        <div class="error">{{ error }}</div>
    {% endif %}
    
    {% if activities %}
        {% for activity in activities %}
        <div class="activity">
            <h3>{{ activity.name }}</h3>
            <p><strong>Type:</strong> {{ activity.type }}</p>
            <p><strong>Date:</strong> {{ activity.start_date_local }}</p>
            <p><strong>Distance:</strong> {{ "%.2f"|format(activity.distance / 1000) }} km</p>
            <p><strong>Duration:</strong> {{ activity.elapsed_time // 60 }} minutes</p>
            {% if activity.average_speed %}
                <p><strong>Average Speed:</strong> {{ "%.2f"|format(activity.average_speed * 3.6) }} km/h</p>
            {% endif %}
        </div>
        {% endfor %}
    {% else %}
        <p>No activities found.</p>
    {% endif %}
</body>
</html>
"""

# --- Flask Routes ---

@app.route('/')
def home():
    """
    Renders the home page with a link to connect to Strava.
    """
    if 'access_token' in session:
        return redirect(url_for('profile'))
    auth_url = (
        f"{STRAVA_AUTH_URL}?"
        f"client_id={STRAVA_CLIENT_ID}&"
        f"redirect_uri={REDIRECT_URI}&"
        f"response_type=code&"
        f"scope={SCOPE}"
    )
    return render_template_string(HTML_TEMPLATE, auth_url=auth_url)

@app.route('/strava/callback')
def strava_callback():
    """
    Handles the Strava OAuth callback, exchanges the code for an access token,
    and stores it in the session.
    """
    code = request.args.get('code')
    if not code:
        return "Error: No code provided", 400

    # Exchange code for access token
    response = requests.post(STRAVA_TOKEN_URL, data={
        'client_id': STRAVA_CLIENT_ID,
        'client_secret': STRAVA_CLIENT_SECRET,
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': REDIRECT_URI
    })

    if response.status_code != 200:
        return f"Error: Unable to fetch access token. Status: {response.status_code}, Response: {response.text}", 400

    data = response.json()
    session['access_token'] = data['access_token']
    session['athlete_data'] = data['athlete']
    
    return redirect(url_for('profile'))

@app.route('/profile')
def profile():
    """
    Fetches the user's profile from Strava and displays it.
    """
    if 'access_token' not in session:
        return redirect(url_for('home'))
    
    athlete_data = session.get('athlete_data')
    if not athlete_data:
        # Try to fetch athlete data from Strava API
        access_token = session['access_token']
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get(f'{STRAVA_API_URL}/athlete', headers=headers)
        
        if response.status_code == 200:
            athlete_data = response.json()
            session['athlete_data'] = athlete_data
        else:
            return f"Error fetching profile data: {response.status_code}", 400
    
    return render_template_string(PROFILE_TEMPLATE, profile=athlete_data)

@app.route('/activities')
def activities():
    """
    Fetches and displays the user's recent activities from Strava.
    """
    if 'access_token' not in session:
        return redirect(url_for('home'))
    
    access_token = session['access_token']
    headers = {'Authorization': f'Bearer {access_token}'}
    
    # Fetch activities from Strava API
    response = requests.get(f'{STRAVA_API_URL}/athlete/activities', 
                          headers=headers, 
                          params={'per_page': 10})  # Get last 10 activities
    
    if response.status_code == 200:
        activities_data = response.json()
        return render_template_string(ACTIVITIES_TEMPLATE, activities=activities_data, error=None)
    else:
        error_msg = f"Error fetching activities: {response.status_code} - {response.text}"
        return render_template_string(ACTIVITIES_TEMPLATE, activities=None, error=error_msg)

@app.route('/logout')
def logout():
    """Logs out the user by clearing the session.
    """
    session.clear()
    return redirect(url_for('home'))

# --- Main entry point ---
if __name__ == '__main__':
    app.run(debug=True, port=5000)