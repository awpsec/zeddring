"""Web interface for Zeddring."""

import os
import logging
from typing import Dict, Any, List, Optional
import datetime
import asyncio
import json

from flask import Flask, render_template, request, jsonify, redirect, url_for, abort
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
    rings = ring_manager.get_all_rings()
    return render_template('index.html', rings=rings)

@app.route('/ring/<int:ring_id>')
def ring_detail(ring_id):
    """Render the ring detail page."""
    ring = ring_manager.get_ring(ring_id)
    if not ring:
        return redirect(url_for('index'))
        
    # Get daily data for today
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    daily_data = ring_manager.get_daily_data(ring_id, today)
    
    return render_template('ring_detail.html', ring=ring.to_dict(), daily_data=daily_data)

@app.route('/api/rings', methods=['GET'])
def get_rings():
    """Get all rings."""
    rings = ring_manager.get_all_rings()
    return jsonify({
        "success": True,
        "rings": rings
    })

@app.route('/api/ring/add', methods=['POST'])
def add_ring():
    """Add a new ring."""
    name = request.form.get('name')
    mac_address = request.form.get('mac_address')
    
    if not name or not mac_address:
        return jsonify({
            "success": False,
            "error": "Name and MAC address are required"
        })
        
    ring_id = ring_manager.add_ring(name, mac_address)
    
    if ring_id:
        return jsonify({
            "success": True,
            "ring_id": ring_id
        })
    else:
        return jsonify({
            "success": False,
            "error": "Failed to add ring"
        })

@app.route('/api/ring/<int:ring_id>/remove', methods=['POST'])
def remove_ring(ring_id):
    """Remove a ring."""
    success = ring_manager.remove_ring(ring_id)
    
    return jsonify({
        "success": success,
        "error": "Failed to remove ring" if not success else None
    })

@app.route('/api/ring/<int:ring_id>/connect', methods=['POST'])
def connect_ring(ring_id):
    """Connect to a ring."""
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
    # Create a new event loop for this request
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Get data from the ring
    data = loop.run_until_complete(ring_manager.get_ring_data(ring_id))
    
    # Close the loop
    loop.close()
    
    if data:
        # Save data to database
        ring_manager.save_ring_data(ring_id, data)
        
        return jsonify({
            "success": True,
            "data": data
        })
    else:
        return jsonify({
            "success": False,
            "error": "Failed to get data from ring"
        })

@app.route('/api/ring/<int:ring_id>/history', methods=['GET'])
def get_ring_history(ring_id):
    """Get ring data history."""
    days = request.args.get('days', 7, type=int)
    
    history = ring_manager.get_ring_history(ring_id, days)
    
    return jsonify({
        "success": True,
        "history": history
    })

@app.route('/api/ring/<int:ring_id>/daily', methods=['GET'])
def get_daily_data(ring_id):
    """Get daily data for a ring."""
    date = request.args.get('date')
    
    daily_data = ring_manager.get_daily_data(ring_id, date)
    
    return jsonify({
        "success": True,
        "data": daily_data
    })

# Custom Jinja2 filter for JSON serialization
@app.template_filter('tojson')
def to_json(value):
    return json.dumps(value)

def start_web_server():
    """Start the web server."""
    # Start the ring manager
    ring_manager.start()
    
    # Start the web server
    app.run(host=WEB_HOST, port=WEB_PORT, debug=DEBUG)


if __name__ == '__main__':
    start_web_server()
