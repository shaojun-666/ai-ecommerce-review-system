"""Model version management with double-buffer hot-reload.

Uses an atomic pointer swap pattern to switch between model versions
without dropping in-flight inference requests. Two slots (A and B) hold
model references; a version registry tracks metadata.

Usage:
    manager = ModelVersionManager(base_dir="./models")
    manager.register_version("v1", "/path/to/v1/model")
    # ... inference uses manager.get_active_model() ...
    manager.activate_version("v2", "/path/to/v2/model")  # atomic swap
"""
import os
import json
import glob
import time
import logging
import threading
from typing import Optional, Callable, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ModelVersion:
    """Metadata for a single model version."""
    version_id: str
    path: str
    created_at: float = 0.0
    metrics: dict = field(default_factory=dict)
    is_quantized: bool = False
    model_type: str = "bert"


class ModelVersionManager:
    """Double-buffer model version manager with atomic hot-swap.

    Maintains two slots but can track any number of registered versions.
    The 'active' slot is read-locked so inference never blocks during swap.
    """

    def __init__(self, base_dir: str = "./models"):
        self.base_dir = base_dir
        self._lock = threading.RLock()
        self._slot_a: Optional[Any] = None
        self._slot_b: Optional[Any] = None
        self._active_slot: str = "a"  # "a" or "b"
        self._versions: dict[str, ModelVersion] = {}
        self._loader_fn: Optional[Callable] = None
        self._registry_path = os.path.join(base_dir, "version_registry.json")
        os.makedirs(base_dir, exist_ok=True)
        self._load_registry()

    def _load_registry(self):
        """Load version registry from disk."""
        if os.path.exists(self._registry_path):
            try:
                with open(self._registry_path) as f:
                    data = json.load(f)
                for v in data.get("versions", []):
                    version = ModelVersion(**v)
                    self._versions[version.version_id] = version
                logger.info("Loaded %d versions from registry", len(self._versions))
            except Exception as e:
                logger.warning("Failed to load version registry: %s", e)

    def _save_registry(self):
        """Save version registry to disk."""
        data = {
            "versions": [
                {
                    "version_id": v.version_id,
                    "path": v.path,
                    "created_at": v.created_at,
                    "metrics": v.metrics,
                    "is_quantized": v.is_quantized,
                    "model_type": v.model_type,
                }
                for v in self._versions.values()
            ]
        }
        with open(self._registry_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def set_loader(self, loader_fn: Callable[[str], Any]):
        """Set the function used to load a model from a path.

        The loader receives a model path and returns a loaded model object.
        """
        self._loader_fn = loader_fn

    def register_version(
        self,
        version_id: str,
        path: str,
        metrics: Optional[dict] = None,
        is_quantized: bool = False,
        model_type: str = "bert",
    ):
        """Register a model version without activating it."""
        version = ModelVersion(
            version_id=version_id,
            path=path,
            created_at=time.time(),
            metrics=metrics or {},
            is_quantized=is_quantized,
            model_type=model_type,
        )
        with self._lock:
            self._versions[version_id] = version
            self._save_registry()
        logger.info("Registered version '%s' at %s", version_id, path)

    def activate_version(self, version_id: str, path: Optional[str] = None) -> bool:
        """Atomically switch the active model to the given version.

        Loads the model into the inactive slot, then flips the pointer.
        If the model fails to load, the active version is unchanged.

        Args:
            version_id: Version identifier.
            path: Model path. If None, uses the registered path.

        Returns:
            True if the swap succeeded, False otherwise.
        """
        if self._loader_fn is None:
            raise RuntimeError("Model loader not set. Call set_loader() first.")

        if version_id not in self._versions:
            # Auto-register if a path is provided
            if path:
                self.register_version(version_id, path)
            else:
                raise ValueError(f"Version '{version_id}' not registered and no path provided")

        version = self._versions[version_id]
        model_path = path or version.path

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model path not found: {model_path}")

        # Load into the inactive slot
        try:
            new_model = self._loader_fn(model_path)
        except Exception as e:
            logger.error("Failed to load model version '%s': %s", version_id, e)
            return False

        # Atomic pointer swap
        with self._lock:
            if self._active_slot == "a":
                self._slot_b = new_model
                self._active_slot = "b"
            else:
                self._slot_a = new_model
                self._active_slot = "a"

            version.path = model_path
            self._versions[version_id] = version
            self._save_registry()

        logger.info("Activated version '%s' (slot %s)", version_id, self._active_slot)
        return True

    def get_active_model(self) -> Optional[Any]:
        """Get the currently active model for inference. Thread-safe."""
        with self._lock:
            if self._active_slot == "a":
                return self._slot_a
            return self._slot_b

    def get_active_version_id(self) -> Optional[str]:
        """Get the ID of the currently active version."""
        for vid, v in self._versions.items():
            if os.path.exists(v.path):
                return vid
        return None

    def list_versions(self) -> list[ModelVersion]:
        """List all registered model versions."""
        return list(self._versions.values())

    def get_version(self, version_id: str) -> Optional[ModelVersion]:
        """Get metadata for a specific version."""
        return self._versions.get(version_id)

    def remove_version(self, version_id: str):
        """Remove a version from the registry (does not delete files)."""
        with self._lock:
            self._versions.pop(version_id, None)
            self._save_registry()
        logger.info("Removed version '%s' from registry", version_id)

    def get_metrics_summary(self) -> dict:
        """Get a summary of all versions and their metrics."""
        return {
            "active_version": self.get_active_version_id(),
            "total_versions": len(self._versions),
            "versions": {
                vid: {
                    "path": v.path,
                    "created_at": v.created_at,
                    "metrics": v.metrics,
                }
                for vid, v in self._versions.items()
            },
        }
