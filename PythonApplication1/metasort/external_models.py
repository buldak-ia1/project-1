from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class EmbeddingBackendResolution:
    provider_name: str
    using_external: bool
    requested_provider: str
    warning: str | None = None


class ExternalEmbeddingBackend:
    provider_name = "none"

    def extract_embedding(self, image_path: Path) -> list[float]:
        raise NotImplementedError


class TransformersClipBackend(ExternalEmbeddingBackend):
    provider_name = "transformers_clip"

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self._processor = None
        self._model = None
        self._torch = None
        self._image_module = None

    @classmethod
    def is_available(cls) -> bool:
        required_modules = ("torch", "transformers", "PIL")
        return all(importlib.util.find_spec(module_name) is not None for module_name in required_modules)

    def extract_embedding(self, image_path: Path) -> list[float]:
        self._ensure_loaded()

        image = self._image_module.open(image_path).convert("RGB")
        inputs = self._processor(images=image, return_tensors="pt")
        device_name = str(self.config.get("device") or "cpu")
        if hasattr(inputs, "to"):
            inputs = inputs.to(device_name)

        with self._torch.no_grad():
            if hasattr(self._model, "get_image_features"):
                outputs = self._model.get_image_features(**inputs)
            else:
                model_outputs = self._model(**inputs)
                outputs = getattr(model_outputs, "image_embeds", None)
                if outputs is None:
                    raise RuntimeError("Configured transformers model does not expose image embeddings.")

        if self.config.get("normalize_embeddings", True):
            outputs = outputs / outputs.norm(dim=-1, keepdim=True)
        return [round(float(value), 6) for value in outputs[0].detach().cpu().tolist()]

    def _ensure_loaded(self) -> None:
        if self._processor is not None and self._model is not None:
            return

        import torch
        from PIL import Image
        from transformers import AutoModel, AutoProcessor

        model_id = str(self.config.get("model_id") or "openai/clip-vit-base-patch32")
        device_name = str(self.config.get("device") or "cpu")
        self._torch = torch
        self._image_module = Image
        self._processor = AutoProcessor.from_pretrained(model_id)
        self._model = AutoModel.from_pretrained(model_id)
        if hasattr(self._model, "to"):
            self._model = self._model.to(device_name)
        if hasattr(self._model, "eval"):
            self._model.eval()


def resolve_embedding_backend(extra_rules: dict[str, Any]) -> tuple[ExternalEmbeddingBackend | None, EmbeddingBackendResolution]:
    config = dict(extra_rules.get("external_model") or {})
    enabled = bool(config.get("enabled", False))
    provider = str(config.get("provider") or "auto")
    requested_provider = provider

    if not enabled:
        return None, EmbeddingBackendResolution(
            provider_name="local_heuristic",
            using_external=False,
            requested_provider=requested_provider,
        )

    if provider in {"auto", "transformers_clip"}:
        if TransformersClipBackend.is_available():
            return TransformersClipBackend(config), EmbeddingBackendResolution(
                provider_name=TransformersClipBackend.provider_name,
                using_external=True,
                requested_provider=requested_provider,
            )
        warning = (
            "External model backend requested, but required packages are missing: "
            "torch, transformers, PIL."
        )
        return None, EmbeddingBackendResolution(
            provider_name="local_heuristic",
            using_external=False,
            requested_provider=requested_provider,
            warning=warning,
        )

    warning = f"Unsupported external model provider '{provider}'. Falling back to local heuristic embedding."
    return None, EmbeddingBackendResolution(
        provider_name="local_heuristic",
        using_external=False,
        requested_provider=requested_provider,
        warning=warning,
    )
