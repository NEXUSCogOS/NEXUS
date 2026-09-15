from __future__ import annotations
import torch
from f5_tts.model import DiT, UnitYield
from f5_tts.infer.utils_infer import (
    DEFAULT_SAMPLE_RATE, load_vocoder, load_model, load_ckpt,
    get_mel_text_token, mel_to_device, preprocess_text
)
import numpy as np
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
import time
import logging

logger = logging.getLogger(__name__)

@dataclass
class VoiceProfile:
    name: str
    cfg_scale: float = 2.0
    nfe: int = 32
    sway: bool = True

VOICE_PROFILES = {
    'sentinel_vi': VoiceProfile('Vietnamese Market Alerts', cfg_scale=2.0, nfe=32),
    'ai_trends_en': VoiceProfile('AI Trends Enthusiastic', cfg_scale=2.1, nfe=32),
    'hotstock_en': VoiceProfile('HotStock Energetic', cfg_scale=2.2, nfe=32),
    'datai_en': VoiceProfile('DatAI Academic', cfg_scale=1.9, nfe=32),
}

class F5TTSGenerator:
    def __init__(self, device: str = 'cpu', precision: str = 'fp16'):
        self.device = device
        self.precision = precision
        self.ckpt_path = 'ckpts/F5TTS_Base'
        self.vocoder_path = 'ckpts/vocos-mel-finetuned'

        self.ckpt = load_ckpt(self.ckpt_path, device)
        self.vocoder = load_vocoder(self.vocoder_path, device)
        self.model = load_model(self.ckpt, device)

    async def generate(
        self,
        text: str,
        profile: str = 'sentinel_vi',
        seed: int = 42,
        speed: float = 1.0
    ) -> Dict[str, Any]:
        profile_config = VOICE_PROFILES.get(profile, VOICE_PROFILES['sentinel_vi'])

        torch.manual_seed(seed)
        np.random.seed(seed)

        start_time = time.time()

        text = preprocess_text(text)
        mel, token_len = get_mel_text_token(text, self.model.args, self.model.mel_stats, self.device)
        mel = mel_to_device(mel, self.device)

        with torch.inference_mode():
            generated = self.model.sample(
                mel=mel,
                steps=profile_config.nfe,
                cfg_scale=profile_config.cfg_scale,
                sway=profile_config.sway
            )

        wav = self.vocoder(generated).squeeze(0).cpu().numpy()

        duration_ms = int((len(wav) / DEFAULT_SAMPLE_RATE) * 1000)
        latency_ms = (time.time() - start_time) * 1000

        return {
            'audio': wav,
            'duration_ms': duration_ms,
            'latency_ms': latency_ms,
            'sample_rate': DEFAULT_SAMPLE_RATE,
            'profile': profile,
            'cost_usd': 0.0,
            'model': 'F5-TTS-Base'
        }

class VoiceGenerator:
    def __init__(self, device: str = 'cpu'):
        self.generator = F5TTSGenerator(device=device)
        self.cost_metrics = {'total_cost': 0.0, 'total_duration_ms': 0}

    async def generate_voice(
        self,
        text: str,
        profile: str = 'sentinel_vi',
        seed: int = 42,
        speed: float = 1.0,
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        result = await self.generator.generate(text, profile, seed, speed)

        if output_path:
            import soundfile as sf
            sf.write(output_path, result['audio'], result['sample_rate'])
            result['output_path'] = output_path

        self.cost_metrics['total_duration_ms'] += result['duration_ms']

        return result

    def get_cost_report(self) -> Dict[str, Any]:
        return {
            'total_duration_seconds': self.cost_metrics['total_duration_ms'] / 1000,
            'total_cost_usd': 0.0,
            'average_latency_ms': (self.cost_metrics['total_duration_ms'] /
                                  max(1, len([1])))  # Placeholder for count
        }
