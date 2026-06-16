"""
Unit tests for Bead Completion Logger utilities.

Tests for session improvements identified in 2026-01-24 reflection.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.utils.bead_completion_logger import (
    log_bead_completion,
    verify_bead_unblocked,
    get_parallel_test_command,
    infer_why_from_bead,
)


class TestInferWhyFromBead:
    """Tests for WHY tag inference."""

    def test_infer_from_bug_label(self):
        """Test bug label maps to bugfix."""
        assert infer_why_from_bead(['bug'], '') == 'bugfix'

    def test_infer_from_feature_label(self):
        """Test feature label maps to feature."""
        assert infer_why_from_bead(['feature'], '') == 'feature'

    def test_infer_from_refactor_label(self):
        """Test refactor label maps to refactor."""
        assert infer_why_from_bead(['refactor'], '') == 'refactor'

    def test_infer_from_security_label(self):
        """Test security label maps to security."""
        assert infer_why_from_bead(['security'], '') == 'security'

    def test_infer_from_title_fix(self):
        """Test title with 'fix' maps to bugfix."""
        assert infer_why_from_bead([], 'Fix authentication bug') == 'bugfix'

    def test_infer_from_title_add(self):
        """Test title with 'add' maps to feature."""
        assert infer_why_from_bead([], 'Add entity extraction') == 'feature'

    def test_infer_from_title_implement(self):
        """Test title with 'implement' maps to feature."""
        assert infer_why_from_bead([], 'Implement chunking profiles') == 'feature'

    def test_infer_from_title_refactor(self):
        """Test title with 'refactor' maps to refactor."""
        assert infer_why_from_bead([], 'Refactor processor module') == 'refactor'

    def test_infer_default(self):
        """Test default is implementation."""
        assert infer_why_from_bead([], 'Some random title') == 'implementation'

    def test_label_takes_precedence(self):
        """Test label takes precedence over title."""
        # Title suggests bugfix, but label says feature
        assert infer_why_from_bead(['feature'], 'Fix bug in feature') == 'feature'

    def test_case_insensitive_label(self):
        """Test labels are case-insensitive."""
        assert infer_why_from_bead(['BUG'], '') == 'bugfix'
        assert infer_why_from_bead(['Feature'], '') == 'feature'

    def test_empty_inputs(self):
        """Test with empty inputs."""
        assert infer_why_from_bead([], '') == 'implementation'


class TestLogBeadCompletion:
    """Tests for bead completion logging."""

    @pytest.fixture
    def mock_kv_store(self):
        """Create mock KV store."""
        mock = Mock()
        mock.set = Mock()
        mock.close = Mock()
        return mock

    def test_creates_entry_with_required_fields(self, mock_kv_store):
        """Test entry has all required fields."""
        entry = log_bead_completion(
            bead_id='test-bead-123',
            project='test-project',
            files_changed=['file1.py', 'file2.py'],
            pattern='Fixed authentication issue',
            kv_store=mock_kv_store
        )

        # Check mandatory tags
        assert 'WHO' in entry
        assert 'WHEN' in entry
        assert 'PROJECT' in entry
        assert 'WHY' in entry

        # Check bead reference
        assert entry['bead_id'] == 'test-bead-123'

        # Check fix details
        assert entry['pattern'] == 'Fixed authentication issue'
        assert entry['files_changed'] == ['file1.py', 'file2.py']
        assert entry['confidence'] == 'HIGH'

    def test_stores_to_kv_with_correct_key(self, mock_kv_store):
        """Test entry is stored with correct key pattern."""
        log_bead_completion(
            bead_id='test-bead-456',
            project='test-project',
            files_changed=['file.py'],
            pattern='Test pattern',
            kv_store=mock_kv_store
        )

        mock_kv_store.set.assert_called_once()
        call_args = mock_kv_store.set.call_args
        assert call_args.kwargs['key'] == 'fixes:codex:test-bead-456'
        # TTL should be in seconds (180 days default = 180 * 24 * 60 * 60)
        assert call_args.kwargs['ttl'] == 180 * 24 * 60 * 60

    def test_includes_title_when_provided(self, mock_kv_store):
        """Test title is included when provided."""
        entry = log_bead_completion(
            bead_id='test-bead',
            project='test-project',
            files_changed=['file.py'],
            pattern='Test',
            title='My Bead Title',
            kv_store=mock_kv_store
        )

        assert entry['bead_title'] == 'My Bead Title'

    def test_infers_why_from_labels(self, mock_kv_store):
        """Test WHY is inferred from labels."""
        entry = log_bead_completion(
            bead_id='test-bead',
            project='test-project',
            files_changed=['file.py'],
            pattern='Test',
            labels=['bug', 'urgent'],
            kv_store=mock_kv_store
        )

        assert entry['WHY'] == 'bugfix'

    def test_includes_tests_added(self, mock_kv_store):
        """Test tests_added is included."""
        entry = log_bead_completion(
            bead_id='test-bead',
            project='test-project',
            files_changed=['file.py'],
            pattern='Test',
            tests_added=['test_file.py'],
            kv_store=mock_kv_store
        )

        assert entry['tests_added'] == ['test_file.py']

    def test_custom_agent_name(self, mock_kv_store):
        """Test custom agent name is used."""
        entry = log_bead_completion(
            bead_id='test-bead',
            project='test-project',
            files_changed=['file.py'],
            pattern='Test',
            agent_name='custom:agent:1.0',
            kv_store=mock_kv_store
        )

        assert entry['WHO'] == 'custom:agent:1.0'

    def test_custom_confidence(self, mock_kv_store):
        """Test custom confidence level."""
        entry = log_bead_completion(
            bead_id='test-bead',
            project='test-project',
            files_changed=['file.py'],
            pattern='Test',
            confidence='LOW',
            kv_store=mock_kv_store
        )

        assert entry['confidence'] == 'LOW'

    def test_when_is_utc_iso8601(self, mock_kv_store):
        """Test WHEN timestamp is UTC ISO8601."""
        entry = log_bead_completion(
            bead_id='test-bead',
            project='test-project',
            files_changed=['file.py'],
            pattern='Test',
            kv_store=mock_kv_store
        )

        # Should be parseable as ISO8601
        timestamp = datetime.fromisoformat(entry['WHEN'].replace('Z', '+00:00'))
        assert timestamp.tzinfo is not None


class TestVerifyBeadUnblocked:
    """Tests for bead unblocked verification."""

    @patch('subprocess.run')
    def test_returns_unblocked_for_no_blockers(self, mock_run):
        """Test returns unblocked when no blockers."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="""
DEPENDS ON
  -> test-blocker-1 [CLOSED]

BLOCKS
  <- test-blocked-1
"""
        )

        result = verify_bead_unblocked('test-bead')

        assert result['unblocked'] is True
        assert result['blockers'] == []
        call = mock_run.call_args
        assert isinstance(call.args[0], list)
        assert call.kwargs['shell'] is False
        assert call.args[0][-1] == 'test-bead'

    @patch('subprocess.run')
    def test_passes_bead_id_as_argument_not_shell_text(self, mock_run):
        """Test malicious bead IDs are not interpolated into a shell command."""
        bead_id = 'test-bead; Remove-Item important'
        mock_run.return_value = MagicMock(returncode=0, stdout='')

        result = verify_bead_unblocked(bead_id)

        assert result['unblocked'] is True
        call = mock_run.call_args
        assert call.kwargs['shell'] is False
        assert isinstance(call.args[0], list)
        assert call.args[0][-1] == bead_id

    @patch('subprocess.run')
    def test_handles_subprocess_timeout(self, mock_run):
        """Test handles subprocess timeout."""
        from subprocess import TimeoutExpired
        mock_run.side_effect = TimeoutExpired('cmd', 30)

        result = verify_bead_unblocked('test-bead')

        assert result['unblocked'] is False

    @patch('subprocess.run')
    def test_handles_subprocess_error(self, mock_run):
        """Test handles subprocess error."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr='Error message'
        )

        result = verify_bead_unblocked('test-bead')

        assert result['unblocked'] is False


class TestGetParallelTestCommand:
    """Tests for parallel test command generation."""

    def test_with_specific_test_files(self):
        """Test command with specific test files."""
        cmd = get_parallel_test_command(
            test_files=['test_a.py', 'test_b.py'],
            project_root='/path/to/project'
        )

        assert 'pytest' in cmd
        assert 'test_a.py' in cmd
        assert 'test_b.py' in cmd
        assert '-n auto' in cmd

    def test_without_test_files(self):
        """Test command without specific files runs all tests."""
        cmd = get_parallel_test_command(
            test_files=[],
            project_root='/path/to/project'
        )

        assert 'tests/' in cmd
        assert '-n auto' in cmd

    def test_custom_workers(self):
        """Test custom worker count."""
        cmd = get_parallel_test_command(
            test_files=['test.py'],
            project_root='/path/to/project',
            workers='4'
        )

        assert '-n 4' in cmd

    def test_includes_project_root(self):
        """Test includes project root in cd command."""
        cmd = get_parallel_test_command(
            test_files=['test.py'],
            project_root='/my/project'
        )

        assert 'cd /my/project' in cmd
