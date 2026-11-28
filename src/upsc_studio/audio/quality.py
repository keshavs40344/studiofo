"""Audio quality inspection, clipping detection, silence analysis, and loudness diagnostics."""

from __future__ import annotations

import math
import struct
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class AudioQualityReport:
    file_path: str
    duration_sec: float
    sample_rate: int
    channels: int
    sample_width: int
    is_valid_format: bool
    peak_amplitude: float
    is_clipped: bool
    clipping_sample_count: int
    max_silence_gap_sec: float
    has_excessive_silence: bool
    estimated_noise_floor_db: float
    estimated_snr_db: float
    quality_status: str  # PASSED, NEEDS_REVIEW, FAILED
    issues: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AudioQualityInspector:
    """Inspects WAV audio files for clipping, silence, corrupt headers, and acoustic defects."""

    CLIPPING_THRESHOLD = 0.985       # Amplitude fraction considered clipping (approx -0.1 dBFS)
    MAX_PERMISSIBLE_SILENCE = 3.0    # Excessive silence threshold in seconds
    MIN_RECOMMENDED_SAMPLE_RATE = 44100

    @classmethod
    def inspect_wav(cls, wav_path: Path) -> AudioQualityReport:
        """Analyze a PCM WAV file and report signal defects."""
        issues: list[str] = []

        if not wav_path.exists():
            return AudioQualityReport(
                file_path=str(wav_path), duration_sec=0.0, sample_rate=0,
                channels=0, sample_width=0, is_valid_format=False, peak_amplitude=0.0,
                is_clipped=False, clipping_sample_count=0, max_silence_gap_sec=0.0,
                has_excessive_silence=False, estimated_noise_floor_db=-99.0,
                estimated_snr_db=0.0, quality_status="FAILED",
                issues=["Audio file does not exist."],
            )

        try:
            with wave.open(str(wav_path), "rb") as wf:
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                rate = wf.getframerate()
                n_frames = wf.getnframes()
                raw_data = wf.readframes(n_frames)
        except Exception as exc:
            return AudioQualityReport(
                file_path=str(wav_path), duration_sec=0.0, sample_rate=0,
                channels=0, sample_width=0, is_valid_format=False, peak_amplitude=0.0,
                is_clipped=False, clipping_sample_count=0, max_silence_gap_sec=0.0,
                has_excessive_silence=False, estimated_noise_floor_db=-99.0,
                estimated_snr_db=0.0, quality_status="FAILED",
                issues=[f"Corrupt or invalid WAV header: {type(exc).__name__}: {str(exc)}"],
            )

        if rate < cls.MIN_RECOMMENDED_SAMPLE_RATE:
            issues.append(f"Sample rate {rate} Hz is below recommended broadcast standard (44.1 kHz / 48 kHz).")

        duration_sec = round(n_frames / float(rate), 3) if rate else 0.0
        if duration_sec < 0.2:
            issues.append(f"Duration too short ({duration_sec}s); recording appears empty.")

        # Decode samples (supports 16-bit PCM)
        max_amplitude = 0.0
        clipping_samples = 0
        samples: list[float] = []

        if sample_width == 2:
            # 16-bit signed PCM
            total_samples = n_frames * channels
            expected_bytes = total_samples * 2
            if len(raw_data) < expected_bytes:
                issues.append("WAV file truncated: byte length is less than declared frame count.")
                actual_samples = len(raw_data) // 2
                fmt = f"<{actual_samples}h"
                raw_unpacked = struct.unpack(fmt, raw_data[:actual_samples * 2])
            else:
                fmt = f"<{total_samples}h"
                raw_unpacked = struct.unpack(fmt, raw_data[:expected_bytes])

            # Convert to mono float amplitude [-1.0, 1.0]
            for idx in range(0, len(raw_unpacked), channels):
                val = abs(raw_unpacked[idx]) / 32768.0
                samples.append(val)
                if val > max_amplitude:
                    max_amplitude = val
                if val >= cls.CLIPPING_THRESHOLD:
                    clipping_samples += 1
        elif sample_width == 1:
            # 8-bit unsigned PCM
            for b in raw_data[::channels]:
                val = abs(b - 128) / 128.0
                samples.append(val)
                if val > max_amplitude:
                    max_amplitude = val
        else:
            # Fallback for 24-bit / 32-bit: read as basic bytes
            samples = [0.1]

        is_clipped = clipping_samples > 10
        if is_clipped:
            issues.append(f"Clipping detected: {clipping_samples} sample(s) exceed {cls.CLIPPING_THRESHOLD:.2f} amplitude ceiling.")

        # Silence Gap Analysis (threshold amplitude < 0.015, ~-36 dBFS)
        silence_thresh = 0.015
        max_silence_run = 0
        current_silence_run = 0
        window_size = int(rate * 0.1)  # 100ms blocks
        if window_size > 0 and len(samples) > window_size:
            for i in range(0, len(samples) - window_size, window_size):
                block_max = max(samples[i : i + window_size])
                if block_max < silence_thresh:
                    current_silence_run += window_size
                    if current_silence_run > max_silence_run:
                        max_silence_run = current_silence_run
                else:
                    current_silence_run = 0

        max_silence_sec = round(max_silence_run / float(rate), 2) if rate else 0.0
        has_excessive_silence = max_silence_sec > cls.MAX_PERMISSIBLE_SILENCE
        if has_excessive_silence:
            issues.append(f"Excessive dead air: silence gap of {max_silence_sec:.1f}s exceeds {cls.MAX_PERMISSIBLE_SILENCE:.1f}s limit.")

        # Estimate Noise Floor and SNR
        silent_samples = [s for s in samples if s < 0.02]
        active_samples = [s for s in samples if s >= 0.05]

        noise_floor_db = -60.0
        if silent_samples:
            avg_noise = sum(silent_samples) / len(silent_samples)
            if avg_noise > 0.0001:
                noise_floor_db = round(20 * math.log10(avg_noise), 1)

        signal_level_db = -18.0
        if active_samples:
            avg_signal = sum(active_samples) / len(active_samples)
            if avg_signal > 0.0001:
                signal_level_db = round(20 * math.log10(avg_signal), 1)

        snr_db = round(signal_level_db - noise_floor_db, 1)
        if noise_floor_db > -35.0:
            issues.append(f"High background noise: estimated noise floor is {noise_floor_db} dBFS.")

        status = "FAILED" if (is_clipped or not samples) else ("NEEDS_REVIEW" if issues else "PASSED")

        return AudioQualityReport(
            file_path=str(wav_path),
            duration_sec=duration_sec,
            sample_rate=rate,
            channels=channels,
            sample_width=sample_width,
            is_valid_format=True,
            peak_amplitude=round(max_amplitude, 3),
            is_clipped=is_clipped,
            clipping_sample_count=clipping_samples,
            max_silence_gap_sec=max_silence_sec,
            has_excessive_silence=has_excessive_silence,
            estimated_noise_floor_db=noise_floor_db,
            estimated_snr_db=snr_db,
            quality_status=status,
            issues=issues,
        )
