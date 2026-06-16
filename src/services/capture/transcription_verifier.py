"""Transcription Verification Service for CAPTURE-001.

Handles transcription of audio/video buffers and verification.

WHO: ephemeral-buffer:1.0.0
WHEN: 2026-01-15T00:00:00Z
PROJECT: memory-mcp-triple-system
WHY: infrastructure (CAPTURE-001)
"""

import os
import asyncio
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Callable, Awaitable
from dataclasses import dataclass
import logging
import aiofiles

from src.integrations.ephemeral_buffer_schema import (
    EphemeralBuffer,
    BufferStatus,
    BufferType,
    TranscriptionResult,
)
from src.services.capture.railway_buffer import RailwayBufferService

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionConfig:
    """Configuration for transcription service."""

    # Transcription service to use
    service: str = "whisper"  # whisper, podbrain, assembly-ai

    # Whisper settings
    whisper_model: str = "base"  # tiny, base, small, medium, large
    whisper_language: str = "en"
    whisper_task: str = "transcribe"  # transcribe or translate

    # Output settings
    output_format: str = "json"  # json, txt, vtt, srt
    output_path: str = ""

    # Quality thresholds
    min_confidence: float = 0.8
    min_word_count: int = 10

    # Processing settings
    max_concurrent: int = 2
    timeout: float = 600.0  # 10 minutes

    # Supported audio/video types
    supported_types: List[BufferType] = None

    # External API settings (for cloud services)
    api_key: Optional[str] = None
    api_url: Optional[str] = None

    def __post_init__(self):
        if not self.output_path:
            self.output_path = os.path.join(
                os.path.expanduser("~"), "Documents", "Transcriptions"
            )

        if self.supported_types is None:
            self.supported_types = [
                BufferType.AUDIO_RECORDING,
                BufferType.VIDEO_RECORDING,
                BufferType.VOICE_MEMO,
                BufferType.MEETING_RECORDING,
                BufferType.PODCAST_CAPTURE,
            ]


@dataclass
class TranscriptionJob:
    """A transcription job in progress."""

    buffer_id: str
    input_path: str
    output_path: str
    started_at: datetime
    status: str = "pending"  # pending, running, completed, failed
    error_message: Optional[str] = None
    result: Optional[TranscriptionResult] = None


class TranscriptionVerifier:
    """Service for transcribing and verifying ephemeral buffer content.

    This service handles:
    - Transcription of audio/video files using Whisper or other services
    - Quality verification (confidence score, word count)
    - Transcript storage and management
    - Background processing queue
    """

    def __init__(
        self,
        railway_service: RailwayBufferService,
        config: Optional[TranscriptionConfig] = None,
        on_transcription_complete: Optional[
            Callable[[EphemeralBuffer, TranscriptionResult], Awaitable[None]]
        ] = None,
        on_transcription_error: Optional[
            Callable[[EphemeralBuffer, str], Awaitable[None]]
        ] = None,
    ):
        """Initialize transcription verifier.

        Args:
            railway_service: Railway buffer service instance
            config: Transcription configuration
            on_transcription_complete: Callback on successful transcription
            on_transcription_error: Callback on transcription error
        """
        self.railway = railway_service
        self.config = config or TranscriptionConfig()
        self._on_complete = on_transcription_complete
        self._on_error = on_transcription_error

        # Job tracking
        self._jobs: Dict[str, TranscriptionJob] = {}
        self._completed_jobs: List[TranscriptionJob] = []

        # Concurrency control
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent)

        # Running state
        self._running = False
        self._process_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the transcription service."""
        if self._running:
            return

        # Ensure output directory exists
        os.makedirs(self.config.output_path, exist_ok=True)

        # Verify Whisper is available
        if self.config.service == "whisper":
            await self._verify_whisper()

        self._running = True

        # Start background processing
        self._process_task = asyncio.create_task(self._process_loop())

        logger.info(f"TranscriptionVerifier started, service: {self.config.service}")

    async def stop(self) -> None:
        """Stop the transcription service."""
        self._running = False

        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
            self._process_task = None

        logger.info("TranscriptionVerifier stopped")

    async def _verify_whisper(self) -> bool:
        """Verify Whisper is installed and accessible.

        Returns:
            True if Whisper is available
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "whisper",
                "--help",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            return process.returncode == 0
        except FileNotFoundError:
            logger.warning("Whisper not found, using fallback")
            return False

    async def _process_loop(self) -> None:
        """Background loop for processing transcription queue."""
        while self._running:
            try:
                # Get buffers ready for transcription
                pending = await self.railway.get_pending_transcription()

                for buffer in pending:
                    if buffer.buffer_type not in self.config.supported_types:
                        continue

                    if buffer.buffer_id in self._jobs:
                        continue  # Already being processed

                    # Queue transcription
                    asyncio.create_task(self._process_buffer(buffer))

                await asyncio.sleep(30)  # Check every 30 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in process loop: {e}")
                await asyncio.sleep(60)

    async def _process_buffer(self, buffer: EphemeralBuffer) -> TranscriptionResult:
        """Process a single buffer for transcription."""
        async with self._semaphore:
            return await self.transcribe_buffer(buffer.buffer_id)

    async def transcribe_buffer(
        self,
        buffer_id: str,
        force: bool = False,
    ) -> Optional[TranscriptionResult]:
        """Transcribe a buffer.

        Args:
            buffer_id: Buffer ID to transcribe
            force: Force re-transcription

        Returns:
            TranscriptionResult if successful
        """
        buffer = await self.railway.get_buffer(buffer_id)
        if not buffer:
            logger.error(f"Buffer not found: {buffer_id}")
            return None

        # Check if already transcribed
        if not force and buffer.status == BufferStatus.TRANSCRIBED:
            return buffer.transcription

        # Check if file exists
        input_path = buffer.local_path
        if not input_path or not os.path.exists(input_path):
            logger.error(f"Local file not found for buffer {buffer_id}")
            return None

        # Check if supported type
        if buffer.buffer_type not in self.config.supported_types:
            logger.warning(f"Unsupported buffer type: {buffer.buffer_type}")
            return None

        # Create job
        output_path = self._get_output_path(buffer)
        job = TranscriptionJob(
            buffer_id=buffer_id,
            input_path=input_path,
            output_path=output_path,
            started_at=datetime.now(timezone.utc),
            status="running",
        )
        self._jobs[buffer_id] = job

        try:
            # Mark buffer as transcribing
            buffer.mark_transcribing()
            await self.railway.update_buffer_status(
                buffer_id, BufferStatus.TRANSCRIBING
            )

            # Run transcription
            result = await self._run_transcription(job)

            if result:
                # Verify quality
                if self._verify_quality(result):
                    result.verified_at = datetime.now(timezone.utc)

                # Update buffer
                buffer.mark_transcribed(result)
                await self.railway.update_buffer_status(
                    buffer_id, BufferStatus.TRANSCRIBED
                )

                job.status = "completed"
                job.result = result

                # Callback
                if self._on_complete:
                    await self._on_complete(buffer, result)

                logger.info(
                    f"Transcribed buffer {buffer_id}: "
                    f"{result.word_count} words, confidence {result.confidence_score:.2f}"
                )

                return result

            else:
                raise Exception("Transcription returned no result")

        except Exception as e:
            error_msg = str(e)
            job.status = "failed"
            job.error_message = error_msg

            buffer.mark_error(error_msg)
            await self.railway.update_buffer_status(buffer_id, BufferStatus.ERROR)

            if self._on_error:
                await self._on_error(buffer, error_msg)

            logger.error(f"Transcription failed for {buffer_id}: {e}")
            return None

        finally:
            self._completed_jobs.append(job)
            del self._jobs[buffer_id]

    def _get_output_path(self, buffer: EphemeralBuffer) -> str:
        """Get output path for transcription.

        Args:
            buffer: Buffer being transcribed

        Returns:
            Output file path
        """
        date_str = buffer.created_at.strftime("%Y-%m-%d")
        base_name = Path(buffer.metadata.original_filename).stem
        ext = (
            ".json"
            if self.config.output_format == "json"
            else f".{self.config.output_format}"
        )

        return os.path.join(
            self.config.output_path, date_str, f"{base_name}_transcript{ext}"
        )

    async def _run_transcription(
        self, job: TranscriptionJob
    ) -> Optional[TranscriptionResult]:
        """Run the actual transcription process.

        Args:
            job: Transcription job

        Returns:
            TranscriptionResult if successful
        """
        if self.config.service == "whisper":
            return await self._run_whisper(job)
        elif self.config.service == "podbrain":
            return await self._run_podbrain(job)
        elif self.config.service == "assembly-ai":
            return await self._run_assemblyai(job)
        else:
            raise RuntimeError(
                f"Unsupported transcription service: {self.config.service}"
            )

    async def _run_whisper(
        self, job: TranscriptionJob
    ) -> Optional[TranscriptionResult]:
        """Run Whisper transcription.

        Args:
            job: Transcription job

        Returns:
            TranscriptionResult if successful
        """
        # Ensure output directory exists
        os.makedirs(os.path.dirname(job.output_path), exist_ok=True)

        # Build command
        cmd = [
            "whisper",
            job.input_path,
            "--model",
            self.config.whisper_model,
            "--language",
            self.config.whisper_language,
            "--task",
            self.config.whisper_task,
            "--output_format",
            self.config.output_format,
            "--output_dir",
            os.path.dirname(job.output_path),
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.config.timeout,
            )

            if process.returncode != 0:
                logger.error(f"Whisper error: {stderr.decode()}")
                return None

            # Parse output
            return await self._parse_whisper_output(job)

        except asyncio.TimeoutError:
            logger.error(f"Whisper timeout for {job.buffer_id}")
            return None
        except FileNotFoundError:
            logger.error("Whisper not found; transcription unavailable")
            raise RuntimeError("Whisper transcription backend is not installed")

    async def _parse_whisper_output(
        self, job: TranscriptionJob
    ) -> Optional[TranscriptionResult]:
        """Parse Whisper output file.

        Args:
            job: Transcription job

        Returns:
            TranscriptionResult if successful
        """
        # Find the output file (Whisper names it based on input)
        input_stem = Path(job.input_path).stem
        output_dir = os.path.dirname(job.output_path)

        json_path = os.path.join(output_dir, f"{input_stem}.json")
        txt_path = os.path.join(output_dir, f"{input_stem}.txt")

        transcript_text = ""
        word_count = 0
        confidence = 0.85  # Default confidence

        if os.path.exists(json_path):
            async with aiofiles.open(json_path, "r") as f:
                content = await f.read()
                data = json.loads(content)

                transcript_text = data.get("text", "")
                word_count = len(transcript_text.split())

                # Calculate average confidence from segments
                segments = data.get("segments", [])
                if segments:
                    confidences = [s.get("avg_logprob", -0.5) for s in segments]
                    # Convert log prob to confidence (rough approximation)
                    avg_logprob = sum(confidences) / len(confidences)
                    confidence = min(1.0, max(0.0, 1.0 + avg_logprob))

        elif os.path.exists(txt_path):
            async with aiofiles.open(txt_path, "r") as f:
                transcript_text = await f.read()
                word_count = len(transcript_text.split())

        if not transcript_text:
            return None

        # Compute checksum
        checksum = hashlib.sha256(transcript_text.encode()).hexdigest()

        return TranscriptionResult(
            transcript_id=f"whisper_{job.buffer_id}",
            transcript_path=json_path if os.path.exists(json_path) else txt_path,
            word_count=word_count,
            confidence_score=confidence,
            language=self.config.whisper_language,
            transcription_service="whisper",
            verification_method="checksum",
            checksum=checksum,
        )

    async def _run_podbrain(
        self, job: TranscriptionJob
    ) -> Optional[TranscriptionResult]:
        """Run PodBrain transcription.

        Args:
            job: Transcription job

        Returns:
            TranscriptionResult if successful
        """
        raise RuntimeError(
            "PodBrain transcription backend is not shipped/configured; "
            "no synthetic transcript is returned"
        )

    async def _run_assemblyai(
        self, job: TranscriptionJob
    ) -> Optional[TranscriptionResult]:
        """Run AssemblyAI transcription.

        Args:
            job: Transcription job

        Returns:
            TranscriptionResult if successful
        """
        raise RuntimeError(
            "AssemblyAI transcription backend is not shipped/configured; "
            "no synthetic transcript is returned"
        )

    def _verify_quality(self, result: TranscriptionResult) -> bool:
        """Verify transcription quality meets thresholds.

        Args:
            result: Transcription result to verify

        Returns:
            True if quality is acceptable
        """
        if result.confidence_score < self.config.min_confidence:
            logger.warning(
                f"Low confidence: {result.confidence_score} < {self.config.min_confidence}"
            )
            return False

        if result.word_count < self.config.min_word_count:
            logger.warning(
                f"Low word count: {result.word_count} < {self.config.min_word_count}"
            )
            return False

        return True

    async def verify_transcription(
        self,
        buffer_id: str,
    ) -> bool:
        """Verify an existing transcription.

        Args:
            buffer_id: Buffer ID to verify

        Returns:
            True if verification passed
        """
        buffer = await self.railway.get_buffer(buffer_id)
        if not buffer or not buffer.transcription:
            return False

        result = buffer.transcription

        # Verify file exists
        if not os.path.exists(result.transcript_path):
            return False

        # Verify checksum
        async with aiofiles.open(result.transcript_path, "r") as f:
            content = await f.read()

        if result.transcript_path.endswith(".json"):
            data = json.loads(content)
            text = data.get("text", "")
        else:
            text = content

        checksum = hashlib.sha256(text.encode()).hexdigest()

        if checksum != result.checksum:
            logger.warning(f"Checksum mismatch for {buffer_id}")
            return False

        # Mark as verified
        result.verified_at = datetime.now(timezone.utc)

        return True

    async def get_pending_transcription(self) -> List[EphemeralBuffer]:
        """Get buffers pending transcription.

        Returns:
            List of buffers ready for transcription
        """
        return await self.railway.get_pending_transcription()

    def get_job_status(self, buffer_id: str) -> Optional[TranscriptionJob]:
        """Get status of a transcription job.

        Args:
            buffer_id: Buffer ID

        Returns:
            Job if found
        """
        return self._jobs.get(buffer_id)

    def get_stats(self) -> Dict[str, Any]:
        """Get transcription service statistics.

        Returns:
            Statistics dictionary
        """
        completed = len([j for j in self._completed_jobs if j.status == "completed"])
        failed = len([j for j in self._completed_jobs if j.status == "failed"])
        total_words = sum(j.result.word_count for j in self._completed_jobs if j.result)
        avg_confidence = 0.0
        if completed > 0:
            avg_confidence = (
                sum(j.result.confidence_score for j in self._completed_jobs if j.result)
                / completed
            )

        return {
            "running": self._running,
            "service": self.config.service,
            "active_jobs": len(self._jobs),
            "completed": completed,
            "failed": failed,
            "total_words_transcribed": total_words,
            "average_confidence": round(avg_confidence, 3),
            "config": {
                "model": self.config.whisper_model,
                "language": self.config.whisper_language,
                "min_confidence": self.config.min_confidence,
                "max_concurrent": self.config.max_concurrent,
            },
        }
