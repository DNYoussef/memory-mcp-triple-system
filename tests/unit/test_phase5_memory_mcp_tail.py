import asyncio
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import pytest

from src.integrations.ephemeral_buffer_schema import BufferType
from src.mcp.tools.beads_tools import BeadsTools
from src.services.capture.railway_buffer import RailwayBufferService, RailwayConfig
from src.services.capture.transcription_verifier import (
    TranscriptionConfig,
    TranscriptionJob,
    TranscriptionVerifier,
)
from src.services.graph_service import GraphService


def test_graph_node_manager_exposes_expected_aging_and_importance_methods(tmp_path):
    graph = GraphService(data_dir=str(tmp_path))
    assert graph.add_chunk_node("chunk:alpha", {"text": "alpha memory"})

    assert graph.increment_node_frequency("chunk:alpha") is True
    assert graph.update_node_decay_score("chunk:alpha") is True
    assert graph.update_node_importance("chunk:alpha", explicit_weight=0.9) is True

    node = graph.get_node("chunk:alpha")
    assert node["frequency"] == 1
    assert 0.0 <= node["decay_score"] <= 1.0
    assert 0.0 <= node["importance"] <= 1.0
    assert graph.get_nodes_by_importance(0.0, 1.0)[0][0] == "chunk:alpha"


def test_unshipped_cloud_transcription_backends_fail_closed(tmp_path):
    input_path = tmp_path / "audio.wav"
    output_path = tmp_path / "audio.json"
    input_path.write_bytes(b"not real audio")
    job = TranscriptionJob(
        buffer_id="buf-1",
        input_path=str(input_path),
        output_path=str(output_path),
        started_at=datetime.now(timezone.utc),
    )
    verifier = TranscriptionVerifier(
        railway_service=None,
        config=TranscriptionConfig(output_path=str(tmp_path)),
    )

    with pytest.raises(RuntimeError, match="PodBrain.*not shipped"):
        asyncio.run(verifier._run_podbrain(job))
    with pytest.raises(RuntimeError, match="AssemblyAI.*not shipped"):
        asyncio.run(verifier._run_assemblyai(job))

    assert output_path.exists() is False


def test_beads_memory_link_creates_graph_edge_not_cli_comment(tmp_path):
    graph = GraphService(data_dir=str(tmp_path))
    tools = BeadsTools(graph_service=graph)
    tools._run_beads_command = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("beads_link_memory must not store graph links as CLI comments")
    )

    result = asyncio.run(
        tools.beads_link_memory(
            task_id="bd-123",
            memory_key="memory-key-7",
            relationship="supports",
        )
    )

    assert result["success"] is True
    assert graph.graph.has_edge("beads:bd-123", "memory:memory-key-7")
    edge = graph.graph.edges["beads:bd-123", "memory:memory-key-7"]
    assert edge["type"] == "supports"
    assert edge["metadata"]["task_id"] == "bd-123"
    assert edge["metadata"]["memory_key"] == "memory-key-7"


def test_beads_memory_link_fails_closed_without_graph_service():
    tools = BeadsTools()

    result = asyncio.run(tools.beads_link_memory("bd-123", "memory-key-7"))

    assert result["success"] is False
    assert "graph service is not configured" in result["error"]


def test_railway_download_url_is_signed_and_requires_token(tmp_path):
    async def exercise():
        service = RailwayBufferService(
            RailwayConfig(
                temp_storage_path=str(tmp_path),
                railway_api_url="https://buffers.example",
                railway_api_token="top-secret",
            )
        )
        buffer = await service.upload_bytes(
            b"payload",
            "clip.wav",
            BufferType.AUDIO_RECORDING,
        )

        signed = await service.get_download_url(buffer.buffer_id, expires_in_seconds=120)
        parsed = urlparse(signed)
        query = parse_qs(parsed.query)

        assert signed != buffer.railway_url
        assert parsed.scheme == "https"
        assert parsed.netloc == "buffers.example"
        assert parsed.path == f"/buffers/{buffer.buffer_id}/download"
        assert query["signature"][0]
        assert query["expires"][0].isdigit()

        service.config.railway_api_token = None
        assert await service.get_download_url(buffer.buffer_id) is None

    asyncio.run(exercise())
