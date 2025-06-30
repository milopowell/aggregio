#app.py
#Main Application file for Aggregio
#Handles Strava OAuth2 authentication and basic API interaction

import os
import requests
from flask import Flask, redirect, request, session, render_template, url_for, flash
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
REDIRECT_URI = "http://127.0.0.1:5000/strava/callback"

#The permissions we want to request from Strava
SCOPE = 'read,activity:read_all'

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
    return render_template('home.html', auth_url=auth_url)

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
    
    return render_template('profile.html', profile=athlete_data)

@app.route('/activities')
@app.route('/activities/<int:page>')
def activities(page=1):
    """
    Fetches and displays the user's activities from Strava with pagination.
    Activities per page is responsive to viewport size.
    """
    if 'access_token' not in session:
        return redirect(url_for('home'))
    
    access_token = session['access_token']
    headers = {'Authorization': f'Bearer {access_token}'}
    
    # Get viewport dimensions from request args (passed from frontend)
    viewport_width = request.args.get('width', type=int, default=1200)
    viewport_height = request.args.get('height', type=int, default=800)
    
    # Calculate activities per page based on viewport size
    def calculate_per_page(width, height):
        # Calculate available space more precisely for full viewport usage
        # Account for header, pagination, and container padding
        header_height = 100  # header + border + margins
        pagination_height = 80  # pagination controls
        container_padding = 40  # top/bottom padding
        
        available_height = height - header_height - pagination_height - container_padding
        available_width = min(width - 40, 1360)  # container max-width minus padding
        
        # Activity card dimensions (including gaps)
        card_width = 340   # 320px + 20px gap
        card_height = 240  # estimated card height + 20px gap
        
        # Calculate grid layout
        cards_per_row = max(1, available_width // card_width)
        rows_that_fit = max(1, available_height // card_height)
        
        # Total cards that fit perfectly in viewport
        total_cards = cards_per_row * rows_that_fit
        
        # Ensure reasonable bounds (minimum 2, maximum 24)
        per_page = max(2, min(24, total_cards))
        
        return per_page
    
    per_page = calculate_per_page(viewport_width, viewport_height)
    
    # Fetch activities from Strava API with pagination
    response = requests.get(f'{STRAVA_API_URL}/athlete/activities', 
                          headers=headers, 
                          params={
                              'per_page': per_page,
                              'page': page
                          })
    
    if response.status_code == 200:
        activities_data = response.json()
        
        # Check if there are more activities (for next page button)
        has_next = len(activities_data) == per_page
        
        # Check if there's a previous page
        has_prev = page > 1
        
        return render_template('activities.html', 
                             activities=activities_data, 
                             error=None,
                             current_page=page,
                             has_next=has_next,
                             has_prev=has_prev,
                             next_page=page + 1,
                             prev_page=page - 1,
                             per_page=per_page)  # Pass per_page to template
    else:
        error_msg = f"Error fetching activities: {response.status_code} - {response.text}"
        return render_template('activities.html', 
                             activities=None, 
                             error=error_msg,
                             current_page=page,
                             has_next=False,
                             has_prev=False,
                             per_page=per_page)
# Route to display a single activity with map
@app.route('/activity/<int:activity_id>')
def activity_detail(activity_id):
    """Display detailed view of a single activity with map"""
    print(f"DEBUG: Accessing activity {activity_id}")
    try:
        # Get activity details
        headers = {'Authorization': f'Bearer {session["access_token"]}'}
        
        # Fetch activity details
        print(f"DEBUG: Making API request for activity {activity_id}")
        activity_response = requests.get(
            f'https://www.strava.com/api/v3/activities/{activity_id}',
            headers=headers
        )
        print(f"DEBUG: API response status: {activity_response.status_code}")
        
        if activity_response.status_code != 200:
            return f"<h1>Error loading activity</h1><p>Status: {activity_response.status_code}</p><a href='/activities'>Back to Activities</a>"
        
        activity = activity_response.json()
        print(f"DEBUG: Activity loaded: {activity.get('name', 'Unknown')}")
        
        # Fetch activity streams for map data
        print(f"DEBUG: Fetching streams for activity {activity_id}")
        streams_response = requests.get(
            f'https://www.strava.com/api/v3/activities/{activity_id}/streams',
            headers=headers,
            params={
                'keys': 'latlng,altitude,time,distance,velocity_smooth',
                'key_by_type': 'true'
            }
        )
        print(f"DEBUG: Streams response status: {streams_response.status_code}")
        
        streams = {}
        if streams_response.status_code == 200:
            streams = streams_response.json()
            print(f"DEBUG: Streams loaded, keys: {list(streams.keys())}")
        
        print(f"DEBUG: Rendering template")
        return render_template('activity_detail.html', 
                             activity=activity, 
                             streams=streams)
        
    except Exception as e:
        print(f"DEBUG: Exception occurred: {str(e)}")
        return f"<h1>Error</h1><p>{str(e)}</p><a href='/activities'>Back to Activities</a>"


def get_activity_streams(activity_id, access_token):
    """Helper function to fetch activity streams from Strava API"""
    headers = {'Authorization': f'Bearer {access_token}'}
    
    try:
        response = requests.get(
            f'https://www.strava.com/api/v3/activities/{activity_id}/streams',
            headers=headers,
            params={
                'keys': 'latlng,altitude,time,distance,velocity_smooth',
                'key_by_type': 'true'
            }
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {}
            
    except Exception as e:
        print(f"Error fetching streams: {e}")
        return {}
# In-memory storage for aggregates (replace with database in production)
user_aggregates = {}

@app.route('/aggregates')
def aggregates():
    """
    Display all user aggregates with create/edit functionality
    """
    if 'access_token' not in session:
        return redirect(url_for('home'))
    
    if 'athlete' not in session:
        return redirect(url_for('profile'))
    
    athlete_id = session['athlete']['id']
    user_aggs = user_aggregates.get(athlete_id, [])
    
    return render_template('aggregates.html', aggregates=user_aggs)

@app.route('/aggregates/new')
def new_aggregate():
    """
    Create a new aggregate - shows activity selection page
    """
    if 'access_token' not in session:
        return redirect(url_for('home'))
    
    # Fetch all activities to choose from
    access_token = session['access_token']
    headers = {'Authorization': f'Bearer {access_token}'}
    
    # Get more activities for selection (up to 200)
    all_activities = []
    page = 1
    per_page = 50
    
    while len(all_activities) < 200:  # Limit to prevent too many API calls
        response = requests.get(f'{STRAVA_API_URL}/athlete/activities', 
                              headers=headers, 
                              params={'per_page': per_page, 'page': page})
        
        if response.status_code == 200:
            activities_data = response.json()
            if not activities_data:  # No more activities
                break
            all_activities.extend(activities_data)
            page += 1
        else:
            break
    
    return render_template('aggregate_form.html', 
                         activities=all_activities, 
                         aggregate=None, 
                         mode='new')

@app.route('/aggregates/<int:aggregate_id>/edit')
def edit_aggregate(aggregate_id):
    """
    Edit an existing aggregate
    """
    if 'access_token' not in session:
        return redirect(url_for('home'))
    
    athlete_id = session['athlete']['id']
    user_aggs = user_aggregates.get(athlete_id, [])
    
    # Find the aggregate
    aggregate = None
    for agg in user_aggs:
        if agg['id'] == aggregate_id:
            aggregate = agg
            break
    
    if not aggregate:
        return redirect(url_for('aggregates'))
    
    # Fetch all activities to choose from
    access_token = session['access_token']
    headers = {'Authorization': f'Bearer {access_token}'}
    
    all_activities = []
    page = 1
    per_page = 50
    
    while len(all_activities) < 200:
        response = requests.get(f'{STRAVA_API_URL}/athlete/activities', 
                              headers=headers, 
                              params={'per_page': per_page, 'page': page})
        
        if response.status_code == 200:
            activities_data = response.json()
            if not activities_data:
                break
            all_activities.extend(activities_data)
            page += 1
        else:
            break
    
    return render_template('aggregate_form.html', 
                         activities=all_activities, 
                         aggregate=aggregate, 
                         mode='edit')

@app.route('/aggregates/save', methods=['POST'])
def save_aggregate():
    """
    Save a new or edited aggregate
    """
    if 'access_token' not in session:
        return redirect(url_for('home'))
    
    athlete_id = session['athlete']['id']
    
    # Get form data
    aggregate_id = request.form.get('aggregate_id', type=int)
    name = request.form.get('name', '').strip()
    selected_activities = request.form.getlist('selected_activities')
    
    if not name:
        return redirect(url_for('aggregates'))
    
    # Initialize user aggregates if not exists
    if athlete_id not in user_aggregates:
        user_aggregates[athlete_id] = []
    
    # Fetch activity details for selected activities
    access_token = session['access_token']
    headers = {'Authorization': f'Bearer {access_token}'}
    
    aggregate_activities = []
    total_distance = 0
    total_time = 0
    total_elevation = 0
    
    for activity_id in selected_activities:
        response = requests.get(f'{STRAVA_API_URL}/activities/{activity_id}', headers=headers)
        if response.status_code == 200:
            activity = response.json()
            aggregate_activities.append({
                'id': activity['id'],
                'name': activity['name'],
                'type': activity['type'],
                'distance': activity['distance'],
                'elapsed_time': activity['elapsed_time'],
                'total_elevation_gain': activity.get('total_elevation_gain', 0),
                'start_date_local': activity['start_date_local']
            })
            
            # Add to totals
            total_distance += activity['distance']
            total_time += activity['elapsed_time']
            total_elevation += activity.get('total_elevation_gain', 0)
    
    # Create or update aggregate
    aggregate_data = {
        'name': name,
        'activities': aggregate_activities,
        'totals': {
            'distance': total_distance,
            'time': total_time,
            'elevation': total_elevation,
            'count': len(aggregate_activities)
        },
        'created_at': datetime.now().isoformat()
    }
    
    if aggregate_id:  # Editing existing
        for i, agg in enumerate(user_aggregates[athlete_id]):
            if agg['id'] == aggregate_id:
                aggregate_data['id'] = aggregate_id
                aggregate_data['created_at'] = agg['created_at']  # Keep original creation date
                user_aggregates[athlete_id][i] = aggregate_data
                break
    else:  # Creating new
        # Generate new ID
        existing_ids = [agg['id'] for agg in user_aggregates[athlete_id]]
        new_id = max(existing_ids) + 1 if existing_ids else 1
        aggregate_data['id'] = new_id
        user_aggregates[athlete_id].append(aggregate_data)
    
    return redirect(url_for('aggregates'))

@app.route('/aggregates/<int:aggregate_id>/delete', methods=['POST'])
def delete_aggregate(aggregate_id):
    """
    Delete an aggregate
    """
    if 'access_token' not in session:
        return redirect(url_for('home'))
    
    athlete_id = session['athlete']['id']
    
    if athlete_id in user_aggregates:
        user_aggregates[athlete_id] = [
            agg for agg in user_aggregates[athlete_id] 
            if agg['id'] != aggregate_id
        ]
    
    return redirect(url_for('aggregates'))

@app.route('/aggregates/<int:aggregate_id>')
def view_aggregate(aggregate_id):
    """
    View a specific aggregate with detailed stats
    """
    if 'access_token' not in session:
        return redirect(url_for('home'))
    
    athlete_id = session['athlete']['id']
    user_aggs = user_aggregates.get(athlete_id, [])
    
    # Find the aggregate
    aggregate = None
    for agg in user_aggs:
        if agg['id'] == aggregate_id:
            aggregate = agg
            break
    
    if not aggregate:
        return redirect(url_for('aggregates'))
    
    return render_template('aggregate_detail.html', aggregate=aggregate)

@app.route('/logout')
def logout():
    """Logs out the user by clearing the session.
    """
    session.clear()
    return redirect(url_for('home'))

# --- Main entry point ---
if __name__ == '__main__':
    app.run(debug=True, port=5000)