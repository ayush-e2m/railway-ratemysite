#!/usr/bin/env python3
"""
Railway-deployable Flask web app for RateMySite analysis with Excel export
"""

import os
import json
import uuid
from typing import List, Generator, Dict, Any

from flask import Flask, render_template, request, Response, stream_with_context, send_file, jsonify
from utils.scraper import stream_analysis
from utils.excel_export import create_excel_report

app = Flask(__name__)

# Configure for Railway deployment
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['UPLOAD_FOLDER'] = 'static/downloads'

# Ensure downloads directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Store analysis results temporarily (in production, use Redis or database)
analysis_cache = {}

TABLE_ROWS = [
    ("Company", "Company"),
    ("URL", "URL"),
    ("Overall Score", "Overall Score"),
    ("Description of Website", "Description of Website"),
    ("Consumer Score", "Audience Perspective → Consumer"),
    ("Developer Score", "Audience Perspective → Developer"),
    ("Investor Score", "Audience Perspective → Investor"),
    ("Clarity Score", "Technical Criteria → Clarity"),
    ("Visual Design Score", "Technical Criteria → Visual Design"),
    ("UX Score", "Technical Criteria → UX"),
    ("Trust Score", "Technical Criteria → Trust"),
    ("Value Prop Score", "Value Proposition"),
]

@app.route("/")
def index():
    """Main page"""
    return render_template("index.html")

@app.route("/stream")
def stream():
    """Stream analysis results"""
    urls = [u.strip() for u in request.args.getlist("u") if u.strip()]
    if not urls:
        return Response("Need at least one ?u= parameter", status=400)
    
    # Generate unique session ID for this analysis
    session_id = str(uuid.uuid4())
    analysis_cache[session_id] = {"urls": urls, "results": []}
    
    def enhanced_stream():
        for event_data in stream_analysis(urls):
            # Cache results for Excel export
            if '"event": "result"' in event_data and '"data":' in event_data:
                try:
                    # Extract result data for caching
                    lines = event_data.strip().split('\n')
                    for line in lines:
                        if line.startswith('data: '):
                            data = json.loads(line[6:])  # Remove 'data: ' prefix
                            if 'data' in data and data.get('data'):
                                analysis_cache[session_id]["results"].append(data['data'])
                            break
                except (json.JSONDecodeError, KeyError):
                    pass
            
            # Add session ID to events for frontend tracking
            if '"event": "init"' in event_data:
                try:
                    lines = event_data.strip().split('\n')
                    for i, line in enumerate(lines):
                        if line.startswith('data: '):
                            data = json.loads(line[6:])
                            data['session_id'] = session_id
                            lines[i] = f'data: {json.dumps(data)}'
                            event_data = '\n'.join(lines) + '\n'
                            break
                except (json.JSONDecodeError, KeyError):
                    pass
            
            yield event_data
    
    return Response(
        stream_with_context(enhanced_stream()), 
        mimetype="text/event-stream",
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'  # Disable nginx buffering if present
        }
    )

@app.route("/download/excel/<session_id>")
def download_excel(session_id):
    """Download analysis results as Excel file"""
    if session_id not in analysis_cache:
        return jsonify({"error": "Session not found or expired"}), 404
    
    cache_data = analysis_cache[session_id]
    results = cache_data["results"]
    
    if not results:
        return jsonify({"error": "No results available for download"}), 400
    
    try:
        # Generate Excel file
        filename = f"ratemysite_analysis_{session_id[:8]}.xlsx"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        create_excel_report(results, filepath, TABLE_ROWS)
        
        # Send file and clean up
        def cleanup():
            try:
                os.remove(filepath)
                # Clean up cache after some time (in production, use proper cleanup)
                if session_id in analysis_cache:
                    del analysis_cache[session_id]
            except OSError:
                pass
        
        response = send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        # Schedule cleanup after response
        response.call_on_close(cleanup)
        return response
        
    except Exception as e:
        app.logger.error(f"Error generating Excel file: {e}")
        return jsonify({"error": "Failed to generate Excel file"}), 500

@app.route("/api/cache/<session_id>")
def get_cache(session_id):
    """Get cached analysis data (for debugging)"""
    if session_id in analysis_cache:
        return jsonify(analysis_cache[session_id])
    return jsonify({"error": "Session not found"}), 404

@app.route("/health")
def health():
    """Health check endpoint for Railway"""
    return {"status": "healthy", "app": "RateMySite Analysis"}

if __name__ == "__main__":
    # Railway provides PORT environment variable
    port = int(os.environ.get("PORT", 5000))
    # Use 0.0.0.0 for Railway deployment
    host = "0.0.0.0" if os.environ.get("RAILWAY_ENVIRONMENT") else "127.0.0.1"
    debug = os.environ.get("FLASK_ENV") == "development"
    
    app.run(
        host=host,
        port=port,
        debug=debug,
        threaded=True
    )
