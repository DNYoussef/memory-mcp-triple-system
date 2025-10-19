"""
Flask Application for Memory Curation UI
Provides web interface for lifecycle tagging and verification of memory chunks.

NASA Rule 10 Compliant: All functions ≤60 LOC
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
from typing import Dict, Any, List
import chromadb
from loguru import logger

from ..services.curation_service import CurationService


app = Flask(__name__, template_folder='templates', static_folder='static')


# Initialize ChromaDB client and CurationService
def init_services() -> CurationService:
    """
    Initialize ChromaDB client and CurationService.

    Returns:
        CurationService instance
    """
    client = chromadb.PersistentClient(path="./data/chroma")
    service = CurationService(
        chroma_client=client,
        collection_name="memory_chunks",
        data_dir="./data"
    )
    logger.info("Initialized CurationService")
    return service


curation_service = init_services()


@app.route('/')
def index():
    """
    Home page - redirects to curation interface.

    Returns:
        Redirect to /curate
    """
    return redirect(url_for('curate'))


@app.route('/curate', methods=['GET'])
def curate():
    """
    Curation interface - displays batch of unverified chunks.

    Returns:
        Rendered template with chunks and preferences
    """
    # Get user preferences
    prefs = curation_service.get_preferences()
    batch_size = prefs.get('batch_size', 20)

    # Get unverified chunks
    chunks = curation_service.get_unverified_chunks(limit=batch_size)

    # Auto-suggest lifecycle for each chunk
    for chunk in chunks:
        chunk['suggested_lifecycle'] = curation_service.auto_suggest_lifecycle(chunk)

    return render_template(
        'curate.html',
        chunks=chunks,
        preferences=prefs,
        lifecycle_options=['permanent', 'temporary', 'ephemeral']
    )


@app.route('/api/curate/tag', methods=['POST'])
def api_tag_lifecycle():
    """
    API endpoint to tag chunk with lifecycle.

    Request JSON:
        {
            "chunk_id": "uuid",
            "lifecycle": "permanent|temporary|ephemeral"
        }

    Returns:
        JSON response with success status
    """
    data = request.get_json()

    # Validate request
    if not data or 'chunk_id' not in data or 'lifecycle' not in data:
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400

    chunk_id = data['chunk_id']
    lifecycle = data['lifecycle']

    # Tag lifecycle
    success = curation_service.tag_lifecycle(chunk_id, lifecycle)

    if success:
        return jsonify({'success': True, 'chunk_id': chunk_id, 'lifecycle': lifecycle})
    else:
        return jsonify({'success': False, 'error': 'Failed to tag chunk'}), 500


@app.route('/api/curate/verify', methods=['POST'])
def api_mark_verified():
    """
    API endpoint to mark chunk as verified.

    Request JSON:
        {
            "chunk_id": "uuid"
        }

    Returns:
        JSON response with success status
    """
    data = request.get_json()

    # Validate request
    if not data or 'chunk_id' not in data:
        return jsonify({'success': False, 'error': 'Missing chunk_id'}), 400

    chunk_id = data['chunk_id']

    # Mark verified
    success = curation_service.mark_verified(chunk_id)

    if success:
        return jsonify({'success': True, 'chunk_id': chunk_id})
    else:
        return jsonify({'success': False, 'error': 'Failed to verify chunk'}), 500


@app.route('/api/curate/time', methods=['POST'])
def api_log_time():
    """
    API endpoint to log curation session time.

    Request JSON:
        {
            "duration_seconds": 180,
            "chunks_curated": 5
        }

    Returns:
        JSON response with success status
    """
    data = request.get_json()

    # Validate request
    if not data or 'duration_seconds' not in data:
        return jsonify({'success': False, 'error': 'Missing duration_seconds'}), 400

    duration = data['duration_seconds']
    chunks_curated = data.get('chunks_curated', 0)

    # Log time
    curation_service.log_time(
        duration_seconds=duration,
        chunks_curated=chunks_curated
    )

    return jsonify({'success': True, 'duration_seconds': duration})


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """
    Settings page - display and update user preferences.

    GET: Display current preferences
    POST: Update preferences and redirect

    Returns:
        Rendered template (GET) or redirect (POST)
    """
    if request.method == 'POST':
        # Update preferences from form
        new_prefs = {
            'user_id': 'default',
            'time_budget_minutes': int(request.form.get('time_budget_minutes', 5)),
            'auto_suggest': request.form.get('auto_suggest') == 'on',
            'weekly_review_day': request.form.get('weekly_review_day', 'sunday'),
            'weekly_review_time': request.form.get('weekly_review_time', '10:00'),
            'batch_size': int(request.form.get('batch_size', 20)),
            'default_lifecycle': request.form.get('default_lifecycle', 'temporary')
        }

        curation_service.save_preferences('default', new_prefs)
        logger.info("Updated user preferences")

        return redirect(url_for('settings'))

    # GET - display current preferences
    prefs = curation_service.get_preferences()
    return render_template('settings.html', preferences=prefs)


@app.route('/api/settings', methods=['GET', 'PUT'])
def api_settings():
    """
    API endpoint for preferences (JSON-based).

    GET: Return current preferences
    PUT: Update preferences

    Returns:
        JSON response with preferences
    """
    if request.method == 'PUT':
        data = request.get_json(silent=True)

        if data is None or not data:
            return jsonify({'success': False, 'error': 'Missing request body'}), 400

        # Save preferences
        try:
            curation_service.save_preferences('default', data)
            return jsonify({'success': True, 'preferences': data})
        except AssertionError as e:
            return jsonify({'success': False, 'error': str(e)}), 400

    # GET - return current preferences
    prefs = curation_service.get_preferences()
    return jsonify(prefs)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
