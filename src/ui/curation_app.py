"""
Flask Application for Memory Curation UI
Provides web interface for lifecycle tagging and verification of memory chunks.

NASA Rule 10 Compliant: All functions ≤60 LOC
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
from typing import Dict, Any, List, Optional
import os
import chromadb
from loguru import logger

from ..services.curation_service import CurationService
from ..indexing.vector_indexer import resolve_persist_dir


app = Flask(__name__, template_folder='templates', static_folder='static')


# Initialize ChromaDB client and CurationService
def init_services() -> CurationService:
    """
    Initialize ChromaDB client and CurationService.

    The data directory honors MEMORY_MCP_DATA_DIR (env-first, consistent with
    service_wiring) and falls back to a project-relative ./data.

    Returns:
        CurationService instance
    """
    data_dir = os.getenv("MEMORY_MCP_DATA_DIR", "./data")
    # Single resolver: honors CHROMA_PERSIST_DIR / MEMORY_MCP_DATA_DIR so the UI
    # opens the same store as the stdio/HTTP server.
    chroma_path = resolve_persist_dir(default=os.path.join(data_dir, "chroma"))
    client = chromadb.PersistentClient(path=chroma_path)
    service = CurationService(
        chroma_client=client,
        collection_name="memory_chunks",
        data_dir=data_dir
    )
    logger.info("Initialized CurationService")
    return service


# Lazily-initialized singleton, kept at module scope so tests can patch it.
# Starts as None so importing this module no longer constructs a ChromaDB client
# (the previous import-time call created ./data/chroma as a side effect, e.g.
# during pytest collection). The service is built on first request instead.
curation_service: Optional[CurationService] = None


def get_curation_service() -> CurationService:
    """Return the process-wide CurationService, initializing on first use.

    A non-None value (including a test mock patched onto ``curation_service``)
    is returned as-is, so the module attribute remains the injection seam.
    """
    global curation_service
    if curation_service is None:
        curation_service = init_services()
    return curation_service


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
    prefs = get_curation_service().get_preferences()
    batch_size = prefs.get('batch_size', 20)

    # Get unverified chunks
    chunks = get_curation_service().get_unverified_chunks(limit=batch_size)

    # Auto-suggest lifecycle for each chunk
    for chunk in chunks:
        chunk['suggested_lifecycle'] = get_curation_service().auto_suggest_lifecycle(chunk)

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
    success = get_curation_service().tag_lifecycle(chunk_id, lifecycle)

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
    success = get_curation_service().mark_verified(chunk_id)

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
    get_curation_service().log_time(
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

        get_curation_service().save_preferences('default', new_prefs)
        logger.info("Updated user preferences")

        return redirect(url_for('settings'))

    # GET - display current preferences
    prefs = get_curation_service().get_preferences()
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
            get_curation_service().save_preferences('default', data)
            return jsonify({'success': True, 'preferences': data})
        except AssertionError as e:
            return jsonify({'success': False, 'error': str(e)}), 400

    # GET - return current preferences
    prefs = get_curation_service().get_preferences()
    return jsonify(prefs)


def _env_flag(name: str, default: bool = False) -> bool:
    """Parse a boolean environment flag."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_run_options() -> Dict[str, Any]:
    """Standalone curation UI defaults to local-only and no debugger."""
    return {
        "debug": _env_flag("MEMORY_MCP_CURATION_DEBUG", False),
        "host": os.getenv("MEMORY_MCP_CURATION_HOST", "127.0.0.1"),
        "port": int(os.getenv("MEMORY_MCP_CURATION_PORT", "5000")),
    }


if __name__ == '__main__':
    app.run(**_get_run_options())
