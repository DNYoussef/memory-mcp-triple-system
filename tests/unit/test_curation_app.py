"""
Unit tests for Flask Curation App
Following TDD (London School) with proper test structure and route validation.
"""

import pytest
import json
from unittest.mock import Mock, MagicMock, patch

from src.ui.curation_app import app, init_services


@pytest.fixture
def client():
    """Create Flask test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_curation_service():
    """Create mock CurationService."""
    service = MagicMock()

    # Default mock behaviors
    service.get_preferences.return_value = {
        'user_id': 'default',
        'time_budget_minutes': 5,
        'auto_suggest': True,
        'weekly_review_day': 'sunday',
        'weekly_review_time': '10:00',
        'batch_size': 20,
        'default_lifecycle': 'temporary'
    }

    service.get_unverified_chunks.return_value = [
        {
            'id': 'chunk1',
            'text': 'Test chunk 1',
            'file_path': '/test/file1.md',
            'chunk_index': 0,
            'lifecycle': 'temporary',
            'verified': False
        },
        {
            'id': 'chunk2',
            'text': 'Test chunk 2',
            'file_path': '/test/file2.md',
            'chunk_index': 1,
            'lifecycle': 'permanent',
            'verified': False
        }
    ]

    service.auto_suggest_lifecycle.return_value = 'temporary'
    service.tag_lifecycle.return_value = True
    service.mark_verified.return_value = True

    return service


class TestIndexRoute:
    """Test suite for index route."""

    def test_index_redirects_to_curate(self, client):
        """Test index route redirects to curate."""
        response = client.get('/')

        assert response.status_code == 302
        assert '/curate' in response.location


class TestCurateRoute:
    """Test suite for curate route."""

    @patch('src.ui.curation_app.curation_service')
    def test_curate_displays_chunks(self, mock_service, client, mock_curation_service):
        """Test curate route displays unverified chunks."""
        mock_service.get_preferences = mock_curation_service.get_preferences
        mock_service.get_unverified_chunks = mock_curation_service.get_unverified_chunks
        mock_service.auto_suggest_lifecycle = mock_curation_service.auto_suggest_lifecycle

        response = client.get('/curate')

        assert response.status_code == 200
        assert b'Memory Curation' in response.data
        assert b'chunk1' in response.data
        assert b'chunk2' in response.data

    @patch('src.ui.curation_app.curation_service')
    def test_curate_respects_batch_size(self, mock_service, client, mock_curation_service):
        """Test curate route uses batch_size from preferences."""
        mock_service.get_preferences = mock_curation_service.get_preferences
        mock_service.get_unverified_chunks = mock_curation_service.get_unverified_chunks
        mock_service.auto_suggest_lifecycle = mock_curation_service.auto_suggest_lifecycle

        client.get('/curate')

        mock_service.get_unverified_chunks.assert_called_once_with(limit=20)

    @patch('src.ui.curation_app.curation_service')
    def test_curate_shows_empty_state(self, mock_service, client):
        """Test curate route shows empty state when no chunks."""
        mock_service.get_preferences.return_value = {'batch_size': 20}
        mock_service.get_unverified_chunks.return_value = []

        response = client.get('/curate')

        assert response.status_code == 200
        assert b'All chunks verified!' in response.data


class TestApiTagLifecycle:
    """Test suite for tag lifecycle API endpoint."""

    @patch('src.ui.curation_app.curation_service')
    def test_tag_lifecycle_success(self, mock_service, client, mock_curation_service):
        """Test successful lifecycle tagging."""
        mock_service.tag_lifecycle = mock_curation_service.tag_lifecycle

        response = client.post(
            '/api/curate/tag',
            json={'chunk_id': 'chunk123', 'lifecycle': 'permanent'},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['chunk_id'] == 'chunk123'
        assert data['lifecycle'] == 'permanent'

    def test_tag_lifecycle_missing_fields(self, client):
        """Test tag lifecycle fails with missing fields."""
        response = client.post(
            '/api/curate/tag',
            json={'chunk_id': 'chunk123'},
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False

    @patch('src.ui.curation_app.curation_service')
    def test_tag_lifecycle_service_error(self, mock_service, client):
        """Test tag lifecycle handles service errors."""
        mock_service.tag_lifecycle.return_value = False

        response = client.post(
            '/api/curate/tag',
            json={'chunk_id': 'chunk123', 'lifecycle': 'permanent'},
            content_type='application/json'
        )

        assert response.status_code == 500
        data = json.loads(response.data)
        assert data['success'] is False


class TestApiMarkVerified:
    """Test suite for mark verified API endpoint."""

    @patch('src.ui.curation_app.curation_service')
    def test_mark_verified_success(self, mock_service, client, mock_curation_service):
        """Test successful verification."""
        mock_service.mark_verified = mock_curation_service.mark_verified

        response = client.post(
            '/api/curate/verify',
            json={'chunk_id': 'chunk123'},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['chunk_id'] == 'chunk123'

    def test_mark_verified_missing_id(self, client):
        """Test verify fails with missing chunk_id."""
        response = client.post(
            '/api/curate/verify',
            json={},
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False

    @patch('src.ui.curation_app.curation_service')
    def test_mark_verified_service_error(self, mock_service, client):
        """Test verify handles service errors."""
        mock_service.mark_verified.return_value = False

        response = client.post(
            '/api/curate/verify',
            json={'chunk_id': 'chunk123'},
            content_type='application/json'
        )

        assert response.status_code == 500
        data = json.loads(response.data)
        assert data['success'] is False


class TestApiLogTime:
    """Test suite for log time API endpoint."""

    @patch('src.ui.curation_app.curation_service')
    def test_log_time_success(self, mock_service, client):
        """Test successful time logging."""
        response = client.post(
            '/api/curate/time',
            json={'duration_seconds': 180, 'chunks_curated': 5},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['duration_seconds'] == 180

        mock_service.log_time.assert_called_once_with(
            duration_seconds=180,
            chunks_curated=5
        )

    def test_log_time_missing_duration(self, client):
        """Test log time fails with missing duration."""
        response = client.post(
            '/api/curate/time',
            json={},
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False


class TestSettingsRoute:
    """Test suite for settings route."""

    @patch('src.ui.curation_app.curation_service')
    def test_settings_get(self, mock_service, client, mock_curation_service):
        """Test settings GET displays preferences."""
        mock_service.get_preferences = mock_curation_service.get_preferences

        response = client.get('/settings')

        assert response.status_code == 200
        assert b'User Preferences' in response.data
        assert b'time_budget_minutes' in response.data

    @patch('src.ui.curation_app.curation_service')
    def test_settings_post(self, mock_service, client):
        """Test settings POST updates preferences."""
        response = client.post(
            '/settings',
            data={
                'time_budget_minutes': '10',
                'batch_size': '15',
                'auto_suggest': 'on',
                'weekly_review_day': 'monday',
                'weekly_review_time': '09:00',
                'default_lifecycle': 'permanent'
            }
        )

        assert response.status_code == 302  # Redirect after POST
        assert '/settings' in response.location

        # Verify save_preferences was called
        mock_service.save_preferences.assert_called_once()
        call_args = mock_service.save_preferences.call_args[0]
        assert call_args[0] == 'default'
        assert call_args[1]['time_budget_minutes'] == 10
        assert call_args[1]['batch_size'] == 15


class TestApiSettings:
    """Test suite for API settings endpoint."""

    @patch('src.ui.curation_app.curation_service')
    def test_api_settings_get(self, mock_service, client, mock_curation_service):
        """Test API settings GET returns JSON."""
        mock_service.get_preferences = mock_curation_service.get_preferences

        response = client.get('/api/settings')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['user_id'] == 'default'
        assert data['time_budget_minutes'] == 5

    @patch('src.ui.curation_app.curation_service')
    def test_api_settings_put(self, mock_service, client):
        """Test API settings PUT updates preferences."""
        prefs = {
            'user_id': 'default',
            'time_budget_minutes': 10,
            'auto_suggest': False,
            'weekly_review_day': 'monday',
            'weekly_review_time': '09:00',
            'batch_size': 15,
            'default_lifecycle': 'permanent'
        }

        response = client.put(
            '/api/settings',
            json=prefs,
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

        mock_service.save_preferences.assert_called_once_with('default', prefs)

    def test_api_settings_put_missing_body(self, client):
        """Test API settings PUT fails with missing body."""
        response = client.put(
            '/api/settings',
            data='',
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False

    @patch('src.ui.curation_app.curation_service')
    def test_api_settings_put_validation_error(self, mock_service, client):
        """Test API settings PUT handles validation errors."""
        mock_service.save_preferences.side_effect = AssertionError("Missing fields")

        response = client.put(
            '/api/settings',
            json={'user_id': 'default'},
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
