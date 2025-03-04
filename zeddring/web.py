"""Web interface for Zeddring."""

import os
import logging
from typing import Dict, Any, List, Optional
import datetime

from flask import Flask, render_template, request, jsonify, redirect, url_for, abort
from flask_cors import CORS

from zeddring.config import WEB_HOST, WEB_PORT, DEBUG
from zeddring.database import Database
from zeddring.ring_manager import RingManager

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
ring_manager = RingManager(db)


@app.route('/')
def index():
    """Render the main dashboard."""
    rings = ring_manager.get_ring_status()
    return render_template('index.html', rings=rings)


@app.route('/ring/<int:ring_id>')
def ring_detail(ring_id):
    """Render the detail page for a specific ring."""
    ring = ring_manager.get_ring_by_id(ring_id)
    if not ring:
        return redirect(url_for('index'))
        
    return render_template('ring_detail.html', ring=ring)


@app.route('/api/rings')
def api_rings():
    """API endpoint to get all rings."""
    rings = ring_manager.get_ring_status()
    return jsonify(rings)


@app.route('/api/ring/<int:ring_id>')
def api_ring(ring_id):
    """API endpoint to get a specific ring."""
    ring = ring_manager.get_ring_by_id(ring_id)
    if not ring:
        return jsonify({"error": "Ring not found"}), 404
    return jsonify(ring)


@app.route('/api/ring/<int:ring_id>/heart-rate')
def api_heart_rate(ring_id):
    """API endpoint to get heart rate data for a specific ring."""
    days = request.args.get('days', default=1, type=int)
    
    # Calculate start and end times
    end_time = datetime.datetime.now()
    start_time = end_time - datetime.timedelta(days=days)
    
    # Get data from database
    data = db.get_heart_rate_data(ring_id, start_time, end_time)
    
    return jsonify(data)


@app.route('/api/ring/<int:ring_id>/steps')
def api_steps(ring_id):
    """API endpoint to get steps data for a specific ring."""
    days = request.args.get('days', default=1, type=int)
    
    # Calculate start and end times
    end_time = datetime.datetime.now()
    start_time = end_time - datetime.timedelta(days=days)
    
    # Get data from database
    data = db.get_steps_data(ring_id, start_time, end_time)
    
    return jsonify(data)


@app.route('/api/ring/<int:ring_id>/heart-rate/stats')
def api_heart_rate_stats(ring_id):
    """API endpoint to get heart rate statistics for a specific ring."""
    days = request.args.get('days', default=30, type=int)
    
    # Get data from database
    data = db.get_daily_heart_rate_stats(ring_id, days)
    
    return jsonify(data)


@app.route('/api/ring/<int:ring_id>/steps/stats')
def api_steps_stats(ring_id):
    """API endpoint to get steps statistics for a specific ring."""
    days = request.args.get('days', default=30, type=int)
    
    # Get data from database
    data = db.get_daily_steps_stats(ring_id, days)
    
    return jsonify(data)


@app.route('/api/ring/<int:ring_id>/rename', methods=['POST'])
def api_rename_ring(ring_id):
    """API endpoint to rename a ring."""
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({"error": "Name is required"}), 400
        
    name = data['name']
    success = ring_manager.rename_ring(ring_id, name)
    
    if success:
        return jsonify({"success": True})
    else:
        return jsonify({"error": "Failed to rename ring"}), 500


@app.route('/api/ring/<int:ring_id>/reboot', methods=['POST'])
def api_reboot_ring(ring_id):
    """API endpoint to reboot a ring."""
    success = ring_manager.reboot_ring(ring_id)
    
    if success:
        return jsonify({"success": True})
    else:
        return jsonify({"error": "Failed to reboot ring"}), 500


@app.route('/api/ring/<int:ring_id>/connect', methods=['POST'])
def api_connect_ring(ring_id):
    """API endpoint to connect to a ring."""
    success = ring_manager.connect_ring(ring_id)
    
    if success:
        return jsonify({"success": True})
    else:
        return jsonify({"error": "Failed to connect to ring"}), 500


@app.route('/api/ring/<int:ring_id>/disconnect', methods=['POST'])
def api_disconnect_ring(ring_id):
    """API endpoint to disconnect from a ring."""
    success = ring_manager.disconnect_ring(ring_id)
    
    if success:
        return jsonify({"success": True})
    else:
        return jsonify({"error": "Failed to disconnect from ring"}), 500


@app.route('/api/ring/add', methods=['POST'])
def api_add_ring():
    """API endpoint to add a new ring."""
    data = request.get_json()
    if not data or 'mac_address' not in data:
        return jsonify({"error": "MAC address is required"}), 400
        
    mac_address = data['mac_address']
    name = data.get('name')
    
    # Add ring to database
    ring_id = db.add_or_update_ring(mac_address, name)
    
    # Reload known rings
    ring_manager._load_known_rings()
    
    return jsonify({"success": True, "ring_id": ring_id})


def start_web_server():
    """Start the web server."""
    # Start the ring manager
    ring_manager.start()
    
    # Start the web server
    app.run(host=WEB_HOST, port=WEB_PORT, debug=DEBUG)


if __name__ == '__main__':
    start_web_server()
