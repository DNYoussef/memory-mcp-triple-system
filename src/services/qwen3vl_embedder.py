"""
Qwen3-VL Multimodal Embedder for Visual Memory Sidecar.

MEM-QWEN-005: Implementation of multimodal embedding service using Qwen3-VL-Embedding-2B.
Supports image, text, and joint image+text embeddings with MRL dimension reduction.

NASA Rule 10 Compliant: All functions <=60 LOC
"""

import time
from typing import List, Dict, Any, Optional
from loguru import logger


class Qwen3VLEmbedder:
    """
    Multimodal embedding using Qwen3-VL-Embedding-2B.

    Generates embeddings for images, text, and joint image+text inputs.
    Supports Matryoshka Representation Learning (MRL) for dimension reduction.

    Model: Qwen/Qwen3-VL-Embedding-2B
    Dimensions: 2048 (native), configurable via MRL (default: 384)
    VRAM: ~8GB (FP16)
    """

    MODEL_NAME = "Qwen/Qwen3-VL-Embedding-2B"
    NATIVE_DIM = 2048
    DEFAULT_MRL_DIM = 384

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        use_mrl: bool = True,
        target_dim: int = 384,
        enabled: bool = True
    ):
        """
        Initialize Qwen3-VL embedder.

        Args:
            model_name: HuggingFace model name (default: Qwen3-VL-Embedding-2B)
            device: 'cuda' or 'cpu' (auto-detect if None)
            use_mrl: Use Matryoshka truncation for dimension reduction
            target_dim: Target dimension when using MRL (default: 384)
            enabled: Enable/disable embedder
        """
        self.model_name = model_name or self.MODEL_NAME
        self._model = None
        self._processor = None
        self._device = device
        self.use_mrl = use_mrl
        self.target_dim = target_dim if use_mrl else self.NATIVE_DIM
        self.enabled = enabled

        logger.info(
            f"Qwen3VLEmbedder initialized: model={self.model_name}, "
            f"target_dim={self.target_dim}, enabled={enabled}"
        )

    @property
    def device(self) -> str:
        """Lazy device detection."""
        if self._device is None:
            try:
                import torch
                self._device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                self._device = "cpu"
        return self._device

    @property
    def model(self):
        """Lazy model loading."""
        if self._model is None and self.enabled:
            self._load_model()
        return self._model

    @property
    def processor(self):
        """Lazy processor loading."""
        if self._processor is None and self.enabled:
            self._load_model()
        return self._processor

    def _load_model(self) -> None:
        """Load Qwen3-VL model and processor."""
        try:
            import torch
            from transformers import AutoModel, AutoProcessor

            logger.info(f"Loading Qwen3-VL model: {self.model_name}")
            start = time.time()

            self._processor = AutoProcessor.from_pretrained(
                self.model_name,
                trust_remote_code=True
            )

            dtype = torch.float16 if self.device == "cuda" else torch.float32
            self._model = AutoModel.from_pretrained(
                self.model_name,
                torch_dtype=dtype,
                trust_remote_code=True
            ).to(self.device)

            load_time = time.time() - start
            logger.info(f"Qwen3-VL loaded in {load_time:.2f}s (device={self.device})")

        except Exception as e:
            logger.error(f"Failed to load Qwen3-VL model: {e}")
            self.enabled = False
            self._model = None
            self._processor = None

    def embed_image(self, image_path: str) -> List[float]:
        """
        Generate embedding for an image.

        Args:
            image_path: Path to image file

        Returns:
            Embedding vector (target_dim dimensions)
        """
        if not self.enabled or self.model is None:
            logger.warning("Qwen3VL embedder not available")
            return [0.0] * self.target_dim

        try:
            import torch
            from PIL import Image

            image = Image.open(image_path).convert("RGB")
            inputs = self.processor(
                images=image,
                return_tensors="pt"
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model.get_image_features(**inputs)
                embedding = outputs[0].cpu().numpy().tolist()

            return self._apply_mrl(embedding)

        except Exception as e:
            logger.error(f"Image embedding failed: {e}")
            return [0.0] * self.target_dim

    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for text query.

        Args:
            text: Query text

        Returns:
            Embedding vector (target_dim dimensions)
        """
        if not self.enabled or self.model is None:
            logger.warning("Qwen3VL embedder not available")
            return [0.0] * self.target_dim

        try:
            import torch

            inputs = self.processor(
                text=text,
                return_tensors="pt"
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model.get_text_features(**inputs)
                embedding = outputs[0].cpu().numpy().tolist()

            return self._apply_mrl(embedding)

        except Exception as e:
            logger.error(f"Text embedding failed: {e}")
            return [0.0] * self.target_dim

    def embed_multimodal(self, image_path: str, caption: str) -> List[float]:
        """
        Generate joint embedding for image+text.

        Args:
            image_path: Path to image file
            caption: Associated text/caption

        Returns:
            Joint embedding vector
        """
        if not self.enabled or self.model is None:
            logger.warning("Qwen3VL embedder not available")
            return [0.0] * self.target_dim

        try:
            import torch
            from PIL import Image

            image = Image.open(image_path).convert("RGB")
            inputs = self.processor(
                images=image,
                text=caption,
                return_tensors="pt"
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model(**inputs)
                # Pool features from last hidden state
                embedding = outputs.last_hidden_state.mean(dim=1)[0].cpu().numpy().tolist()

            return self._apply_mrl(embedding)

        except Exception as e:
            logger.error(f"Multimodal embedding failed: {e}")
            return [0.0] * self.target_dim

    def _apply_mrl(self, embedding: List[float]) -> List[float]:
        """Apply Matryoshka truncation if enabled."""
        if self.use_mrl and len(embedding) > self.target_dim:
            return embedding[:self.target_dim]
        return embedding

    def is_available(self) -> bool:
        """Check if embedder is available and enabled."""
        return self.enabled and self.model is not None

    def get_info(self) -> Dict[str, Any]:
        """Get embedder configuration info."""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "native_dim": self.NATIVE_DIM,
            "target_dim": self.target_dim,
            "use_mrl": self.use_mrl,
            "enabled": self.enabled,
            "loaded": self._model is not None
        }
