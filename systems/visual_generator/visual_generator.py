import os
import json
import time
import hashlib
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import numpy as np
from threading import Lock
import pickle

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from diffusers import FluxPipeline, ControlNetModel, AutoencoderKL
from transformers import CLIPProcessor, CLIPModel, CLIPVisionModel
import xgboost as xgb
from scipy import linalg
from PIL import Image
import cv2

logger = logging.getLogger(__name__)


@dataclass
class GenerationConfig:
    model_id: str = "black-forest-labs/FLUX.1-dev"
    height: int = 1024
    width: int = 1024
    num_inference_steps: int = 28
    guidance_scale: float = 7.5
    seed: Optional[int] = None
    control_strength: float = 0.7
    batch_size: int = 4
    enable_attention_slicing: bool = True
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    dtype: torch.dtype = torch.float16 if torch.cuda.is_available() else torch.float32


@dataclass
class CostMetrics:
    tokens_used: int = 0
    compute_time_seconds: float = 0.0
    vram_peak_mb: float = 0.0
    images_generated: int = 0
    cost_usd: float = 0.0
    timestamp: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


class CLIPThumbnailAnalyzer:
    def __init__(self, device: str = "cuda", dtype: torch.dtype = torch.float16):
        self.device = device
        self.dtype = dtype
        self.clip_model = CLIPVisionModel.from_pretrained(
            "openai/clip-vit-large-patch14",
            torch_dtype=dtype
        ).to(device).eval()
        self.clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-large-patch14")

    def extract_features(self, image: Image.Image) -> np.ndarray:
        with torch.no_grad():
            inputs = self.clip_processor(images=image, return_tensors="pt").to(self.device)
            outputs = self.clip_model(**inputs)
            features = outputs.pooler_output.cpu().numpy()
        return features.flatten()


class CTRPredictor:
    def __init__(self, model_path: Optional[str] = None, feature_dim: int = 768):
        self.feature_dim = feature_dim
        self.model = None
        self.scaler_params = None

        if model_path and os.path.exists(model_path):
            self.load(model_path)
        else:
            self._initialize_default_model()

    def _initialize_default_model(self):
        X_dummy = np.random.randn(100, self.feature_dim)
        y_dummy = np.random.binomial(1, 0.3, 100)

        self.model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=7,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            device="cuda",
            tree_method="gpu_hist"
        )
        self.model.fit(X_dummy, y_dummy)

    def predict_ctr(self, features: np.ndarray) -> float:
        if len(features.shape) == 1:
            features = features.reshape(1, -1)

        prob = self.model.predict_proba(features)[0, 1]
        return float(prob)

    def predict_batch(self, features_list: List[np.ndarray]) -> np.ndarray:
        features = np.vstack(features_list)
        probs = self.model.predict_proba(features)[:, 1]
        return probs

    def save(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.model.save_model(path)

    def load(self, path: str):
        self.model = xgb.XGBClassifier()
        self.model.load_model(path)


class FVDCalculator:
    def __init__(self, device: str = "cuda"):
        self.device = device
        self.i3d = self._load_i3d_weights()

    def _load_i3d_weights(self):
        try:
            from pytorch_i3d import I3D
            i3d = I3D(num_classes=400, modality="rgb")
            i3d = i3d.to(self.device).eval()
            return i3d
        except ImportError:
            logger.warning("pytorch_i3d not available, using stub FVD calculator")
            return None

    def calculate_fvd(self,
                     real_frames: List[np.ndarray],
                     generated_frames: List[np.ndarray],
                     sample_size: int = 2048) -> float:
        if self.i3d is None:
            return self._stub_fvd_calculation(real_frames, generated_frames)

        with torch.no_grad():
            real_features = self._extract_i3d_features(real_frames)
            gen_features = self._extract_i3d_features(generated_frames)

        return self._compute_fvd_score(real_features, gen_features)

    def _extract_i3d_features(self, frames: List[np.ndarray]) -> np.ndarray:
        frames_tensor = torch.from_numpy(
            np.stack(frames).transpose(3, 0, 1, 2)
        ).float().to(self.device) / 255.0

        if frames_tensor.shape[0] < 8:
            pad_size = 8 - frames_tensor.shape[0]
            frames_tensor = torch.cat([
                frames_tensor,
                frames_tensor[-1:].repeat(pad_size, 1, 1, 1)
            ], dim=0)

        with torch.no_grad():
            features = self.i3d(frames_tensor.unsqueeze(0))

        return features.cpu().numpy()

    def _compute_fvd_score(self, real_feat: np.ndarray, gen_feat: np.ndarray) -> float:
        mu_real = np.mean(real_feat, axis=0)
        mu_gen = np.mean(gen_feat, axis=0)

        cov_real = np.cov(real_feat.T)
        cov_gen = np.cov(gen_feat.T)

        diff = mu_real - mu_gen
        cov_mean = linalg.sqrtm(cov_real @ cov_gen).real

        fvd = np.sqrt(
            np.sum(diff**2) +
            np.trace(cov_real + cov_gen - 2*cov_mean)
        )

        return float(fvd)

    def _stub_fvd_calculation(self,
                             real_frames: List[np.ndarray],
                             gen_frames: List[np.ndarray]) -> float:
        real_mean = np.mean(np.array(real_frames), axis=(0, 1, 2))
        gen_mean = np.mean(np.array(gen_frames), axis=(0, 1, 2))
        return float(np.sqrt(np.sum((real_mean - gen_mean)**2)))


class ControlNetStyleManager:
    def __init__(self, device: str = "cuda", dtype: torch.dtype = torch.float16):
        self.device = device
        self.dtype = dtype
        self.controlnets = {}
        self._load_default_controlnets()

    def _load_default_controlnets(self):
        controlnet_models = [
            ("canny", "thibaud/controlnet-sd21-canny-diffusers"),
            ("depth", "diffusers/controlnet-depth-sdxl"),
        ]

        for name, model_id in controlnet_models:
            try:
                cn = ControlNetModel.from_pretrained(
                    model_id,
                    torch_dtype=self.dtype
                )
                self.controlnets[name] = cn.to(self.device)
            except Exception as e:
                logger.warning(f"Failed to load ControlNet {name}: {e}")

    def get_controlnet(self, style: str) -> Optional[ControlNetModel]:
        return self.controlnets.get(style)

    def extract_style_condition(self,
                               image: Image.Image,
                               style: str) -> Optional[torch.Tensor]:
        if style == "canny":
            return self._extract_canny(image)
        elif style == "depth":
            return self._extract_depth(image)
        return None

    def _extract_canny(self, image: Image.Image) -> torch.Tensor:
        img_np = np.array(image.resize((512, 512)))
        if len(img_np.shape) == 3:
            img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)

        edges = cv2.Canny(img_np, 100, 200)
        canny = Image.fromarray(edges)

        tensor = torch.from_numpy(np.array(canny)).float().unsqueeze(0).unsqueeze(0) / 255.0
        return tensor.to(self.device)

    def _extract_depth(self, image: Image.Image) -> torch.Tensor:
        try:
            from transformers import pipeline
            depth_pipe = pipeline("depth-estimation", model="Intel/dpt-large")
            depth = depth_pipe(image)["depth"]
            depth_np = np.array(depth.resize((512, 512)))
        except ImportError:
            depth_np = np.random.rand(512, 512)

        tensor = torch.from_numpy(depth_np).float().unsqueeze(0).unsqueeze(0)
        return (tensor - tensor.min()) / (tensor.max() - tensor.min() + 1e-6)


class FluxGenerator:
    def __init__(self, config: GenerationConfig = GenerationConfig()):
        self.config = config
        self.device = config.device
        self.dtype = config.dtype

        self.pipeline = FluxPipeline.from_pretrained(
            config.model_id,
            torch_dtype=config.dtype
        ).to(self.device)

        self.clip_analyzer = CLIPThumbnailAnalyzer(device=self.device, dtype=self.dtype)
        self.ctr_predictor = CTRPredictor()
        self.controlnet_manager = ControlNetStyleManager(device=self.device, dtype=self.dtype)
        self.fvd_calculator = FVDCalculator(device=self.device)

        self.cost_metrics = CostMetrics(timestamp=datetime.now().isoformat())
        self.metrics_lock = Lock()

        if config.enable_attention_slicing:
            self.pipeline.enable_attention_slicing()

    def generate(self,
                prompt: str,
                negative_prompt: str = "",
                style: Optional[str] = None,
                style_image: Optional[Image.Image] = None,
                seed: Optional[int] = None,
                **kwargs) -> Tuple[Image.Image, Dict[str, Any]]:

        start_time = time.time()
        vram_before = torch.cuda.memory_allocated(self.device) if torch.cuda.is_available() else 0

        if seed is None:
            seed = self.config.seed or int(time.time())

        generator = torch.Generator(device=self.device).manual_seed(seed)

        generation_kwargs = {
            "prompt": prompt,
            "height": self.config.height,
            "width": self.config.width,
            "num_inference_steps": self.config.num_inference_steps,
            "guidance_scale": self.config.guidance_scale,
            "generator": generator,
        }

        if negative_prompt:
            generation_kwargs["negative_prompt"] = negative_prompt

        if style and style_image:
            controlnet = self.controlnet_manager.get_controlnet(style)
            if controlnet:
                condition = self.controlnet_manager.extract_style_condition(style_image, style)
                if condition is not None:
                    generation_kwargs["controlnet"] = controlnet
                    generation_kwargs["control_image"] = style_image
                    generation_kwargs["controlnet_conditioning_scale"] = self.config.control_strength

        generation_kwargs.update(kwargs)

        with torch.no_grad():
            output = self.pipeline(**generation_kwargs)

        image = output.images[0]

        compute_time = time.time() - start_time
        vram_after = torch.cuda.memory_allocated(self.device) if torch.cuda.is_available() else 0
        vram_peak = max(0, (vram_after - vram_before) / 1024 / 1024)

        features = self.clip_analyzer.extract_features(image)
        ctr_score = self.clip_analyzer.clip_model.config.hidden_size if hasattr(
            self.clip_analyzer.clip_model, 'config'
        ) else 768

        metrics = {
            "seed": seed,
            "prompt": prompt,
            "style": style,
            "compute_time": compute_time,
            "vram_peak_mb": vram_peak,
            "ctr_score": float(self.ctr_predictor.predict_ctr(features)),
            "features_dim": len(features),
        }

        with self.metrics_lock:
            self.cost_metrics.images_generated += 1
            self.cost_metrics.compute_time_seconds += compute_time
            self.cost_metrics.vram_peak_mb = max(self.cost_metrics.vram_peak_mb, vram_peak)
            self.cost_metrics.cost_usd += (compute_time * 0.0001)

        return image, metrics

    def batch_generate(self,
                      prompts: List[str],
                      style: Optional[str] = None,
                      style_image: Optional[Image.Image] = None,
                      seed_base: Optional[int] = None,
                      **kwargs) -> List[Tuple[Image.Image, Dict[str, Any]]]:

        results = []

        for i, prompt in enumerate(prompts):
            seed = (seed_base + i) if seed_base else None
            image, metrics = self.generate(
                prompt=prompt,
                style=style,
                style_image=style_image,
                seed=seed,
                **kwargs
            )
            results.append((image, metrics))

        return results

    def generate_with_fvd_validation(self,
                                    prompt: str,
                                    reference_frames: List[np.ndarray],
                                    max_fvd: float = 30.0,
                                    max_retries: int = 3,
                                    **kwargs) -> Tuple[Optional[Image.Image], Dict[str, Any]]:

        for attempt in range(max_retries):
            image, metrics = self.generate(prompt, **kwargs)

            generated_frames = [np.array(image)]
            fvd_score = self.fvd_calculator.calculate_fvd(reference_frames, generated_frames)

            metrics["fvd_score"] = fvd_score
            metrics["fvd_valid"] = fvd_score < max_fvd
            metrics["attempt"] = attempt + 1

            if fvd_score < max_fvd:
                return image, metrics

        return None, {"error": f"Failed FVD validation after {max_retries} attempts", "last_fvd": fvd_score}

    def get_cost_report(self) -> Dict[str, Any]:
        with self.metrics_lock:
            return self.cost_metrics.to_dict()

    def reset_cost_metrics(self):
        with self.metrics_lock:
            self.cost_metrics = CostMetrics(timestamp=datetime.now().isoformat())

    def save_checkpoint(self, path: str):
        checkpoint = {
            "config": asdict(self.config),
            "cost_metrics": self.cost_metrics.to_dict(),
            "ctr_model_state": self.ctr_predictor.model.get_booster().save_raw("json")
                if self.ctr_predictor.model else None,
        }

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, 'w') as f:
            json.dump(checkpoint, f, indent=2, default=str)

    def load_checkpoint(self, path: str):
        with open(path, 'r') as f:
            checkpoint = json.load(f)

        self.config = GenerationConfig(**checkpoint.get("config", {}))
        self.cost_metrics = CostMetrics(**checkpoint.get("cost_metrics", {}))


class BatchProcessor:
    def __init__(self,
                 generator: FluxGenerator,
                 batch_size: int = 4,
                 output_dir: str = "./generated_visuals"):
        self.generator = generator
        self.batch_size = batch_size
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = hashlib.md5(
            str(time.time()).encode()
        ).hexdigest()[:8]

    def process_batch(self,
                     prompts: List[str],
                     style: Optional[str] = None,
                     style_image: Optional[Image.Image] = None,
                     save_images: bool = True,
                     **kwargs) -> Dict[str, Any]:

        session_dir = self.output_dir / self.session_id
        session_dir.mkdir(exist_ok=True)

        results = {
            "session_id": self.session_id,
            "prompts": prompts,
            "generated_images": [],
            "metrics": [],
            "cost_summary": {},
        }

        for batch_idx in range(0, len(prompts), self.batch_size):
            batch_prompts = prompts[batch_idx:batch_idx + self.batch_size]

            batch_results = self.generator.batch_generate(
                batch_prompts,
                style=style,
                style_image=style_image,
                seed_base=batch_idx,
                **kwargs
            )

            for img_idx, (image, metrics) in enumerate(batch_results):
                global_idx = batch_idx + img_idx

                if save_images:
                    img_path = session_dir / f"image_{global_idx:04d}.png"
                    image.save(img_path)
                    metrics["image_path"] = str(img_path)

                results["generated_images"].append(image)
                results["metrics"].append(metrics)

        results["cost_summary"] = self.generator.get_cost_report()

        manifest_path = session_dir / "manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump({
                "session_id": results["session_id"],
                "prompts": results["prompts"],
                "metrics": results["metrics"],
                "cost_summary": results["cost_summary"],
            }, f, indent=2)

        return results


def create_visual_generator(config: Optional[GenerationConfig] = None) -> FluxGenerator:
    if config is None:
        config = GenerationConfig()

    return FluxGenerator(config)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    config = GenerationConfig(
        batch_size=2,
        num_inference_steps=28,
        control_strength=0.7,
    )

    generator = create_visual_generator(config)

    test_prompt = "A neon-lit cyberpunk city street at night with holographic billboards"

    image, metrics = generator.generate(test_prompt)
    print(f"Generated image with metrics: {metrics}")
    print(f"Cost report: {generator.get_cost_report()}")

    batch_processor = BatchProcessor(generator, batch_size=2)
    prompts = [
        "A futuristic AI neural network visualization",
        "Vietnamese marketplace at golden hour",
        "Quantum computing abstract representation",
    ]

    results = batch_processor.process_batch(prompts, save_images=True)
    print(f"Batch processing complete. Session ID: {results['session_id']}")
    print(f"Total cost: ${results['cost_summary']['cost_usd']:.4f}")
