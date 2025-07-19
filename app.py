#app.py
#Main Application file for Aggregio
#Handles Strava OAuth2 authentication and basic API interaction

import os
import requests
from flask import Flask, redirect, request, session, render_template, url_for, flash
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Key for session management
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

@app.route('/home')
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
    session['athlete_data'] = data['athlete'] # Stored as 'athlete_data'
    
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
    if 'access_token' not in session:
        return redirect(url_for('home'))
        
    try:
        # Get activity details
        headers = {'Authorization': f'Bearer {session["access_token"]}'}
        
        # Fetch activity details
        activity_response = requests.get(
            f'https://www.strava.com/api/v3/activities/{activity_id}',
            headers=headers
        )
        
        if activity_response.status_code != 200:
            flash(f"Error loading activity: {activity_response.status_code}", 'error')
            return redirect(url_for('activities'))
        
        activity = activity_response.json()
        
        # Fetch activity streams for map data
        streams_response = requests.get(
            f'https://www.strava.com/api/v3/activities/{activity_id}/streams',
            headers=headers,
            params={
                'keys': 'latlng,altitude,time,distance,velocity_smooth',
                'key_by_type': 'true'
            }
        )
        
        streams = {}
        if streams_response.status_code == 200:
            streams = streams_response.json()
        
        return render_template('activity_detail.html', 
                             activity=activity, 
                             streams=streams)
        
    except Exception as e:
        flash(f"An unexpected error occurred: {str(e)}", 'error')
        return redirect(url_for('activities'))


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
@app.route('/aggregates')
def aggregates():
    """
    Fetches and displays ALL of a user's activities from Strava.
    """
    if 'access_token' not in session:
        return redirect(url_for('home'))

    access_token = session['access_token']
    headers = {'Authorization': f'Bearer {access_token}'}
    
    activities_list = []
    page = 1
    # Strava's max per_page is 200, using this minimizes API calls
    per_page = 200 

    while True:
        try:
            # Fetch a page of activities
            response = requests.get(
                f'{STRAVA_API_URL}/athlete/activities',
                headers=headers,
                params={'per_page': per_page, 'page': page}
            )
            response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)

            data = response.json()

            # If the page is empty, we've fetched all activities
            if not data:
                break
            
            # Add the fetched activities to our list
            activities_list.extend(data)
            
            # If we received fewer activities than we asked for, it must be the last page
            if len(data) < per_page:
                break

            # Go to the next page
            page += 1

        except requests.exceptions.RequestException as e:
            flash(f"An error occurred while fetching activities from Strava: {e}", "error")
            return render_template('aggregates.html', activities=[], error=str(e))

    # Render the template with the complete list of activities
    return render_template('aggregates.html', activities=activities_list, error=None)

@app.route('/logout')
def logout():
    """
    Clears the user session and redirects to the home page.
    """
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

# --- Main entry point ---
if __name__ == '__main__':
    app.run(debug=True, port=5000)
