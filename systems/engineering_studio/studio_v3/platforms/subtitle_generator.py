from __future__ import annotations
from faster_whisper import WhisperModel
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class SubtitleGenerator:
    def __init__(self, model_size: str = 'large-v3', device: str = 'cpu'):
        self.model = WhisperModel(model_size, device=device, compute_type='int8')
        self.supported_languages = ['en', 'vi', 'zh', 'ja', 'ko', 'es', 'fr', 'de']

    async def generate_subtitles(
        self,
        audio_path: str,
        language: str = 'auto',
        output_format: str = 'vtt'
    ) -> Dict[str, Any]:
        segments, info = self.model.transcribe(
            audio_path,
            language=None if language == 'auto' else language,
            beam_size=5
        )

        subtitle_data = {
            'subtitle_file': None,
            'duration_ms': int(info.duration * 1000) if hasattr(info, 'duration') else 0,
            'word_count': 0,
            'confidence': [],
            'language_detected': info.language if hasattr(info, 'language') else 'unknown',
            'segments': []
        }

        for segment in segments:
            text = segment.text.strip()
            subtitle_data['segments'].append({
                'start': int(segment.start * 1000),
                'end': int(segment.end * 1000),
                'text': text,
                'confidence': segment.confidence if hasattr(segment, 'confidence') else 0.95
            })
            subtitle_data['word_count'] += len(text.split())
            subtitle_data['confidence'].append(
                segment.confidence if hasattr(segment, 'confidence') else 0.95
            )

        output_path = Path(audio_path).stem + f'.{output_format}'
        self._write_subtitle_file(subtitle_data['segments'], str(output_path), output_format)
        subtitle_data['subtitle_file'] = str(output_path)
        subtitle_data['confidence'] = float(np.mean(subtitle_data['confidence'])) if subtitle_data['confidence'] else 0.95

        return subtitle_data

    def _write_subtitle_file(self, segments: List[Dict], output_path: str, format_type: str = 'vtt'):
        with open(output_path, 'w', encoding='utf-8') as f:
            if format_type == 'vtt':
                f.write('WEBVTT\n\n')
                for seg in segments:
                    f.write(self._ms_to_timecode(seg['start']) + ' --> ' +
                           self._ms_to_timecode(seg['end']) + '\n')
                    f.write(seg['text'] + '\n\n')
            else:
                for i, seg in enumerate(segments, 1):
                    f.write(f'{i}\n')
                    f.write(self._ms_to_srt_timecode(seg['start']) + ' --> ' +
                           self._ms_to_srt_timecode(seg['end']) + '\n')
                    f.write(seg['text'] + '\n\n')

    @staticmethod
    def _ms_to_timecode(ms: int) -> str:
        total_seconds = ms / 1000
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = total_seconds % 60
        return f'{hours:02d}:{minutes:02d}:{seconds:06.3f}'

    @staticmethod
    def _ms_to_srt_timecode(ms: int) -> str:
        total_seconds = ms / 1000
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        millis = int((total_seconds % 1) * 1000)
        return f'{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}'
