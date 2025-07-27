# app.py

from flask import Flask, render_template, request, jsonify, url_for
from flask_socketio import SocketIO, emit
import secrets # For generating secure random session IDs
import datetime
import os # Import the os module for environment variables

# Initialize Flask app
app = Flask(__name__)

# Set a secret key for Flask sessions.
# In a production environment like Heroku, it's best to set this via an environment variable.
# For local development, it will use the default 'your_default_secret_key_for_dev'.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_default_secret_key_for_dev_replace_this_in_prod')

# Initialize SocketIO.
# cors_allowed_origins="*" is used for simplicity in this demo.
# In production, you should restrict this to your specific frontend domain(s).
socketio = SocketIO(app, cors_allowed_origins="*")

# In-memory storage for active sessions and their latest location data.
# IMPORTANT: In a real, persistent application, this would be a database (e.g., SQLite, PostgreSQL).
# This dictionary will be reset every time the Flask server restarts (e.g., on deployment, or if it crashes).
# Format: {session_id: {'name': 'session_name', 'latitude': None, 'longitude': None, 'timestamp': None}}
active_sessions = {}

# --- Flask Routes ---

@app.route('/')
def index():
    """
    Renders the main page where users can generate tracking links.
    """
    return render_template('index.html')

@app.route('/track/<session_id>')
def recipient_page(session_id):
    """
    Renders the page for the recipient to grant location permission.
    """
    if session_id not in active_sessions:
        # If session ID is not found, redirect to an error page or main page
        # In a real app, you might log this or redirect to a more user-friendly error.
        return "Session not found or expired.", 404
    
    session_name = active_sessions[session_id].get('name', 'Unnamed Session')
    return render_template('recipient.html', session_id=session_id, session_name=session_name)

@app.route('/tracker/<session_id>')
def tracker_page(session_id):
    """
    Renders the tracker dashboard page to display location updates.
    """
    if session_id not in active_sessions:
        # If session ID is not found, redirect to an error page or main page
        return "Session not found or expired.", 404

    session_name = active_sessions[session_id].get('name', 'Unnamed Session')
    return render_template('tracker.html', session_id=session_id, session_name=session_name)

@app.route('/generate_link', methods=['POST'])
def generate_link():
    """
    Generates a new unique session ID and stores it in active_sessions.
    Returns the recipient and tracker URLs.
    """
    session_id = secrets.token_urlsafe(16) # Generate a secure, URL-safe ID
    session_name = request.json.get('session_name', f"Session {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    active_sessions[session_id] = {
        'name': session_name,
        'latitude': None,
        'longitude': None,
        'timestamp': None
    }
    
    # Construct full URLs for the client.
    # _external=True is important for generating absolute URLs for sharing.
    recipient_url = url_for('recipient_page', session_id=session_id, _external=True)
    tracker_url = url_for('tracker_page', session_id=session_id, _external=True)
    
    return jsonify({
        'session_id': session_id,
        'session_name': session_name,
        'recipient_url': recipient_url,
        'tracker_url': tracker_url
    })

# --- SocketIO Event Handlers ---

@socketio.on('connect')
def handle_connect():
    """
    Handles new WebSocket connections.
    Prints a message to the server console when a client connects.
    """
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    """
    Handles WebSocket disconnections.
    Prints a message to the server console when a client disconnects.
    """
    print(f"Client disconnected: {request.sid}")

@socketio.on('report_location')
def handle_report_location(data):
    """
    Receives location data from the recipient page (via WebSocket)
    and emits it to all connected clients (specifically the tracker page).
    `data` is expected to be a dictionary with 'session_id', 'latitude', 'longitude', 'timestamp'.
    """
    session_id = data.get('session_id')
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    timestamp = data.get('timestamp')

    if session_id and session_id in active_sessions:
        # Update the in-memory record for this session
        active_sessions[session_id]['latitude'] = latitude
        active_sessions[session_id]['longitude'] = longitude
        active_sessions[session_id]['timestamp'] = timestamp
        
        # Emit the location update to all connected clients.
        # In a more complex app, you might use Socket.IO rooms to only send to relevant trackers.
        emit('location_update', {
            'session_id': session_id,
            'latitude': latitude,
            'longitude': longitude,
            'timestamp': timestamp
        }, broadcast=True) # broadcast=True sends to all connected clients

        print(f"Location reported for session {session_id}: Lat={latitude}, Lon={longitude}")
    else:
        print(f"Received location for unknown or expired session: {session_id}")

# --- Main execution block for local development ---
if __name__ == '__main__':
    # This block is primarily for local development and testing.
    # When deployed to Heroku, Gunicorn (specified in your Procfile) will
    # handle running the Flask application and Socket.IO.
    # Heroku will provide the PORT environment variable.
    # For local testing, you can run this file directly.
    # Use 0.0.0.0 to make it accessible on your local network (e.g., from your phone)
    # if you use your computer's IP address.
    port = int(os.environ.get("PORT", 5000)) # Use PORT env var if available, else 5000
    socketio.run(app, debug=True, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
