"""Web interface for Zeddring."""

import os
import logging
from typing import Dict, Any, List, Optional
import datetime
import asyncio
import json

from flask import Flask, render_template, request, jsonify, redirect, url_for, abort, current_app
from flask_cors import CORS

from zeddring.config import WEB_HOST, WEB_PORT, DEBUG
from zeddring.database import Database
from zeddring.ring_manager import RingManager, get_ring_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("zeddring.web")

# Create Flask app
app = Flask(__name__, 
            template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
            static_folder=os.path.join(os.path.dirname(__file__), 'static'))
CORS(app)

# Initialize database and ring manager
db = Database()
ring_manager = None

def init_app(db_path=None):
    """Initialize the app with the ring manager."""
    global ring_manager
    ring_manager = get_ring_manager(db_path)
    return app

@app.route('/')
def index():
    """Render the dashboard page."""
    ring_manager = current_app.config.get('RING_MANAGER')
    if not ring_manager:
        return "Ring manager not available", 500
        
    rings = ring_manager.get_ring_status()
    return render_template('index.html', rings=rings)

@app.route('/ring/<int:ring_id>')
def ring_detail(ring_id):
    """Render the ring detail page."""
    ring_manager = current_app.config.get('RING_MANAGER')
    if not ring_manager:
        return "Ring manager not available", 500
        
    ring_data = ring_manager.get_ring_data(ring_id)
    if not ring_data:
        return "Ring not found", 404
        
    return render_template('ring_detail.html', ring=ring_data)

@app.route('/api/rings')
def api_rings():
    """API endpoint to get all rings."""
    ring_manager = current_app.config.get('RING_MANAGER')
    if not ring_manager:
        return jsonify({"error": "Ring manager not available"}), 500
        
    rings = ring_manager.get_ring_status()
    return jsonify(rings)

@app.route('/api/ring/<int:ring_id>')
def api_ring_detail(ring_id):
    """API endpoint to get ring details."""
    ring_manager = current_app.config.get('RING_MANAGER')
    if not ring_manager:
        return jsonify({"error": "Ring manager not available"}), 500
        
    ring_data = ring_manager.get_ring_data(ring_id)
    if not ring_data:
        return jsonify({"error": "Ring not found"}), 404
        
    return jsonify(ring_data)

@app.route('/add_ring', methods=['GET', 'POST'])
def add_ring():
    """Add a new ring."""
    if request.method == 'POST':
        name = request.form.get('name')
        mac_address = request.form.get('mac_address')
        
        if not name or not mac_address:
            return "Name and MAC address are required", 400
            
        database = current_app.config.get('DATABASE')
        if not database:
            return "Database not available", 500
            
        ring_id = database.add_ring(name, mac_address)
        return redirect(url_for('index'))
        
    return render_template('add_ring.html')

@app.route('/api/ring/<int:ring_id>/remove', methods=['POST'])
def remove_ring(ring_id):
    """Remove a ring."""
    ring_manager = current_app.config.get('RING_MANAGER')
    if not ring_manager:
        return jsonify({"error": "Ring manager not available"}), 500
        
    success = ring_manager.remove_ring(ring_id)
    
    return jsonify({
        "success": success,
        "error": "Failed to remove ring" if not success else None
    })

@app.route('/api/ring/<int:ring_id>/connect', methods=['POST'])
def connect_ring(ring_id):
    """Connect to a ring."""
    ring_manager = current_app.config.get('RING_MANAGER')
    if not ring_manager:
        return jsonify({"error": "Ring manager not available"}), 500
        
    # Create a new event loop for this request
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Connect to the ring
    success = loop.run_until_complete(ring_manager.connect_ring(ring_id))
    
    # Close the loop
    loop.close()
    
    return jsonify({
        "success": success,
        "error": "Failed to connect to ring" if not success else None
    })

@app.route('/api/ring/<int:ring_id>/disconnect', methods=['POST'])
def disconnect_ring(ring_id):
    """Disconnect from a ring."""
    ring_manager = current_app.config.get('RING_MANAGER')
    if not ring_manager:
        return jsonify({"error": "Ring manager not available"}), 500
        
    # Create a new event loop for this request
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Disconnect from the ring
    success = loop.run_until_complete(ring_manager.disconnect_ring(ring_id))
    
    # Close the loop
    loop.close()
    
    return jsonify({
        "success": success,
        "error": "Failed to disconnect from ring" if not success else None
    })

@app.route('/api/ring/<int:ring_id>/data', methods=['GET'])
def get_ring_data(ring_id):
    """Get data from a ring."""
    ring_manager = current_app.config.get('RING_MANAGER')
    if not ring_manager:
        return jsonify({"error": "Ring manager not available"}), 500
        
    # Get data from the ring
    data = ring_manager.get_ring_data(ring_id)
    
    if data:
        return jsonify({
            "success": True,
            "data": data
        })
    else:
        return jsonify({
            "success": False,
            "error": "Failed to get data from ring"
        })

@app.route('/api/ring/<int:ring_id>/heart-rate', methods=['GET'])
def get_heart_rate_data(ring_id):
    """Get heart rate data for a ring."""
    days = request.args.get('days', 1, type=int)
    
    database = current_app.config.get('DATABASE')
    if not database:
        return jsonify({"error": "Database not available"}), 500
        
    # Get heart rate data
    heart_rate_data = database.get_heart_rate_data(ring_id, limit=100)
    
    return jsonify([
        {'value': row['value'], 'timestamp': row['timestamp']}
        for row in heart_rate_data
    ])

@app.route('/api/ring/<int:ring_id>/heart-rate/stats', methods=['GET'])
def get_heart_rate_stats(ring_id):
    """Get heart rate statistics for a ring."""
    days = request.args.get('days', 30, type=int)
    
    database = current_app.config.get('DATABASE')
    if not database:
        return jsonify({"error": "Database not available"}), 500
        
    # Get heart rate stats
    stats = database.get_daily_heart_rate_stats(ring_id, days)
    
    return jsonify(stats)

@app.route('/api/ring/<int:ring_id>/steps/stats', methods=['GET'])
def get_steps_stats(ring_id):
    """Get steps statistics for a ring."""
    days = request.args.get('days', 30, type=int)
    
    database = current_app.config.get('DATABASE')
    if not database:
        return jsonify({"error": "Database not available"}), 500
        
    # Get steps stats
    stats = database.get_daily_steps_stats(ring_id, days)
    
    return jsonify(stats)

@app.route('/api/ring/<int:ring_id>/history', methods=['GET'])
def get_ring_history(ring_id):
    """Get ring data history."""
    days = request.args.get('days', 7, type=int)
    
    ring_manager = current_app.config.get('RING_MANAGER')
    if not ring_manager:
        return jsonify({"error": "Ring manager not available"}), 500
        
    history = ring_manager.get_ring_history(ring_id, days)
    
    return jsonify({
        "success": True,
        "history": history
    })

@app.route('/api/ring/<int:ring_id>/daily', methods=['GET'])
def get_daily_data(ring_id):
    """Get daily data for a ring."""
    date = request.args.get('date')
    
    ring_manager = current_app.config.get('RING_MANAGER')
    if not ring_manager:
        return jsonify({"error": "Ring manager not available"}), 500
        
    daily_data = ring_manager.get_daily_data(ring_id, date)
    
    return jsonify({
        "success": True,
        "data": daily_data
    })

# Custom Jinja2 filter for JSON serialization
@app.template_filter('tojson')
def to_json(value):
    return json.dumps(value)

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors."""
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    return render_template('500.html'), 500

def start_web_server():
    """Start the web server."""
    # Start the ring manager
    ring_manager = get_ring_manager()
    ring_manager.start()
    
    # Start the web server
    app.config['RING_MANAGER'] = ring_manager
    app.config['DATABASE'] = db
    app.run(host=WEB_HOST, port=WEB_PORT, debug=DEBUG)


if __name__ == '__main__':
    start_web_server()
