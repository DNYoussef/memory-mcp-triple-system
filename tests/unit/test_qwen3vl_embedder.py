"""
Unit tests for Qwen3VLEmbedder.

MEM-QWEN-006: Tests for multimodal embedding service.

Tests:
1. Initialization and configuration
2. Device detection
3. MRL dimension reduction
4. Image embedding (mocked)
5. Text embedding (mocked)
6. Multimodal embedding (mocked)
7. Error handling
"""

import pytest
from unittest.mock import Mock, patch

from src.services.qwen3vl_embedder import Qwen3VLEmbedder


class TestQwen3VLEmbedderInitialization:
    """Test Qwen3VLEmbedder initialization."""

    def test_initialization_default_model(self):
        """Test default model selection."""
        embedder = Qwen3VLEmbedder(enabled=False)
        assert embedder.model_name == "Qwen/Qwen3-VL-Embedding-2B"
        assert embedder.enabled == False

    def test_initialization_custom_model(self):
        """Test custom model name."""
        custom_model = "custom/my-vl-model"
        embedder = Qwen3VLEmbedder(model_name=custom_model, enabled=False)
        assert embedder.model_name == custom_model

    def test_initialization_mrl_enabled(self):
        """Test MRL dimension reduction enabled by default."""
        embedder = Qwen3VLEmbedder(enabled=False)
        assert embedder.use_mrl == True
        assert embedder.target_dim == 384

    def test_initialization_mrl_disabled(self):
        """Test MRL dimension reduction disabled."""
        embedder = Qwen3VLEmbedder(use_mrl=False, enabled=False)
        assert embedder.use_mrl == False
        assert embedder.target_dim == 2048  # Native dimension

    def test_initialization_custom_target_dim(self):
        """Test custom target dimension."""
        embedder = Qwen3VLEmbedder(target_dim=512, enabled=False)
        assert embedder.target_dim == 512

    def test_initialization_explicit_device(self):
        """Test explicit device setting."""
        embedder = Qwen3VLEmbedder(device="cpu", enabled=False)
        assert embedder._device == "cpu"

    def test_initialization_lazy_model_loading(self):
        """Test that model is not loaded until accessed."""
        embedder = Qwen3VLEmbedder(enabled=True)
        assert embedder._model is None
        assert embedder._processor is None


class TestQwen3VLEmbedderDevice:
    """Test device detection."""

    def test_device_auto_detect_cuda(self):
        """Test CUDA device detection."""
        with patch('torch.cuda.is_available', return_value=True):
            embedder = Qwen3VLEmbedder(enabled=False)
            assert embedder.device == "cuda"

    def test_device_auto_detect_cpu(self):
        """Test CPU fallback when CUDA unavailable."""
        with patch('torch.cuda.is_available', return_value=False):
            embedder = Qwen3VLEmbedder(enabled=False)
            embedder._device = None  # Reset to trigger auto-detect
            assert embedder.device == "cpu"

    def test_device_explicit_override(self):
        """Test explicit device overrides auto-detection."""
        with patch('torch.cuda.is_available', return_value=True):
            embedder = Qwen3VLEmbedder(device="cpu", enabled=False)
            assert embedder.device == "cpu"


class TestQwen3VLEmbedderMRL:
    """Test Matryoshka Representation Learning dimension reduction."""

    def test_apply_mrl_truncates(self):
        """Test MRL truncation."""
        embedder = Qwen3VLEmbedder(target_dim=384, use_mrl=True, enabled=False)
        long_embedding = [0.1] * 2048
        result = embedder._apply_mrl(long_embedding)
        assert len(result) == 384

    def test_apply_mrl_preserves_short(self):
        """Test MRL preserves embeddings shorter than target."""
        embedder = Qwen3VLEmbedder(target_dim=384, use_mrl=True, enabled=False)
        short_embedding = [0.1] * 256
        result = embedder._apply_mrl(short_embedding)
        assert len(result) == 256

    def test_apply_mrl_disabled_no_truncation(self):
        """Test no truncation when MRL disabled."""
        embedder = Qwen3VLEmbedder(use_mrl=False, enabled=False)
        long_embedding = [0.1] * 2048
        result = embedder._apply_mrl(long_embedding)
        assert len(result) == 2048


class TestQwen3VLEmbedderImageEmbedding:
    """Test image embedding generation."""

    @pytest.fixture
    def mock_embedder(self):
        """Create embedder with mocked model."""
        embedder = Qwen3VLEmbedder(enabled=True)
        embedder._model = Mock()
        embedder._processor = Mock()
        return embedder

    def test_embed_image_disabled_returns_zeros(self):
        """Test disabled embedder returns zero vector."""
        embedder = Qwen3VLEmbedder(enabled=False)
        result = embedder.embed_image("test.png")
        assert len(result) == 384
        assert all(v == 0.0 for v in result)

    def test_embed_image_model_not_loaded_returns_zeros(self):
        """Test unloaded model returns zero vector."""
        embedder = Qwen3VLEmbedder(enabled=True)
        # Don't load model, just mark as enabled
        result = embedder.embed_image("nonexistent.png")
        assert len(result) == 384

    @patch('PIL.Image.open')
    def test_embed_image_with_mock(self, mock_image_open, mock_embedder):
        """Test image embedding with mocked model."""
        import torch

        # Setup mocks
        mock_image = Mock()
        mock_image.convert.return_value = mock_image
        mock_image_open.return_value = mock_image

        mock_embedder._processor.return_value = {"pixel_values": torch.zeros(1, 3, 224, 224)}
        mock_embedder._model.get_image_features.return_value = [torch.rand(2048)]

        result = mock_embedder.embed_image("test.png")

        assert len(result) == 384  # MRL truncated
        mock_image_open.assert_called_once()


class TestQwen3VLEmbedderTextEmbedding:
    """Test text embedding generation."""

    def test_embed_text_disabled_returns_zeros(self):
        """Test disabled embedder returns zero vector."""
        embedder = Qwen3VLEmbedder(enabled=False)
        result = embedder.embed_text("test query")
        assert len(result) == 384
        assert all(v == 0.0 for v in result)

    def test_embed_text_model_not_loaded_returns_zeros(self):
        """Test unloaded model returns zero vector."""
        embedder = Qwen3VLEmbedder(enabled=True)
        result = embedder.embed_text("test query")
        assert len(result) == 384


class TestQwen3VLEmbedderMultimodalEmbedding:
    """Test multimodal embedding generation."""

    def test_embed_multimodal_disabled_returns_zeros(self):
        """Test disabled embedder returns zero vector."""
        embedder = Qwen3VLEmbedder(enabled=False)
        result = embedder.embed_multimodal("test.png", "test caption")
        assert len(result) == 384
        assert all(v == 0.0 for v in result)


class TestQwen3VLEmbedderHelpers:
    """Test helper methods."""

    def test_is_available_when_disabled(self):
        """Test is_available returns False when disabled."""
        embedder = Qwen3VLEmbedder(enabled=False)
        assert embedder.is_available() == False

    def test_is_available_when_model_not_loaded(self):
        """Test is_available returns False when the model is not loaded.

        V-QWEN: is_available() reads the `model` property, which LAZY-LOADS via
        _load_model() whenever enabled and _model is None. Calling it bare made
        the test depend on whether the model actually loads on this machine/run
        (it failed where the load succeeded). Patch _load_model to a no-op so
        the property cannot pull in a real model; _model stays None and the
        assertion is hermetic. (Setting _model=None alone is insufficient - the
        property would re-trigger the load.)
        """
        with patch.object(Qwen3VLEmbedder, "_load_model", return_value=None):
            embedder = Qwen3VLEmbedder(enabled=True)
            embedder._model = None
            embedder._processor = None
            assert embedder.is_available() == False

    def test_is_available_when_enabled_and_loaded(self):
        """Test is_available returns True when enabled and loaded."""
        embedder = Qwen3VLEmbedder(enabled=True)
        embedder._model = Mock()  # Simulate loaded model
        assert embedder.is_available() == True

    def test_get_info(self):
        """Test get_info returns correct information."""
        embedder = Qwen3VLEmbedder(enabled=False)
        info = embedder.get_info()

        assert "model_name" in info
        assert "device" in info
        assert "native_dim" in info
        assert "target_dim" in info
        assert "use_mrl" in info
        assert "enabled" in info
        assert "loaded" in info

        assert info["native_dim"] == 2048
        assert info["target_dim"] == 384
        assert info["enabled"] == False
        assert info["loaded"] == False


class TestQwen3VLEmbedderModelLoading:
    """Test model loading behavior."""

    def test_lazy_model_loading(self):
        """Test that model is not loaded until accessed."""
        embedder = Qwen3VLEmbedder(enabled=True)
        assert embedder._model is None

    @patch.object(Qwen3VLEmbedder, '_load_model')
    def test_model_loads_on_access(self, mock_load):
        """Test model loads when model property is accessed."""
        mock_load.return_value = None

        embedder = Qwen3VLEmbedder(enabled=True)
        _ = embedder.model

        mock_load.assert_called_once()

    @patch.object(Qwen3VLEmbedder, '_load_model')
    def test_model_load_failure_disables_service(self, mock_load):
        """Test that model load failure disables the service."""
        mock_load.side_effect = Exception("Model load failed")

        embedder = Qwen3VLEmbedder(enabled=True)
        # Access model triggers _load_model which will fail
        # Since _load_model catches exception and sets enabled=False
        mock_load.side_effect = None
        mock_load.return_value = None

        embedder = Qwen3VLEmbedder(enabled=True)
        model = embedder.model

        assert model is None


class TestQwen3VLEmbedderConstants:
    """Test class constants."""

    def test_model_name_constant(self):
        """Test MODEL_NAME constant."""
        assert Qwen3VLEmbedder.MODEL_NAME == "Qwen/Qwen3-VL-Embedding-2B"

    def test_native_dim_constant(self):
        """Test NATIVE_DIM constant."""
        assert Qwen3VLEmbedder.NATIVE_DIM == 2048

    def test_default_mrl_dim_constant(self):
        """Test DEFAULT_MRL_DIM constant."""
        assert Qwen3VLEmbedder.DEFAULT_MRL_DIM == 384
