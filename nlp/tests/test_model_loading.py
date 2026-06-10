"""Tests for model version management and hot-reload."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import tempfile


class TestModelVersionManager:
    def test_register_version(self):
        """Verify version registration and retrieval."""
        from src.models.versioning import ModelVersionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelVersionManager(base_dir=tmpdir)
            manager.register_version("v1", "/fake/path/v1", metrics={"accuracy": 0.85})

            versions = manager.list_versions()
            assert len(versions) == 1
            assert versions[0].version_id == "v1"
            assert versions[0].metrics["accuracy"] == 0.85

    def test_register_multiple_versions(self):
        """Verify multiple version registration."""
        from src.models.versioning import ModelVersionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelVersionManager(base_dir=tmpdir)
            manager.register_version("v1", "/fake/path/v1")
            manager.register_version("v2", "/fake/path/v2")

            assert len(manager.list_versions()) == 2

    def test_get_version(self):
        """Verify specific version retrieval."""
        from src.models.versioning import ModelVersionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelVersionManager(base_dir=tmpdir)
            manager.register_version("v1", "/fake/path/v1")
            manager.register_version("v2", "/fake/path/v2")

            v1 = manager.get_version("v1")
            assert v1 is not None
            assert v1.version_id == "v1"

            missing = manager.get_version("v3")
            assert missing is None

    def test_remove_version(self):
        """Verify version removal from registry."""
        from src.models.versioning import ModelVersionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelVersionManager(base_dir=tmpdir)
            manager.register_version("v1", "/fake/path/v1")
            manager.register_version("v2", "/fake/path/v2")

            manager.remove_version("v1")
            assert len(manager.list_versions()) == 1
            assert manager.list_versions()[0].version_id == "v2"

    def test_persist_registry_across_instances(self):
        """Verify registry survives manager re-initialization."""
        from src.models.versioning import ModelVersionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager1 = ModelVersionManager(base_dir=tmpdir)
            manager1.register_version("v1", "/fake/path/v1", metrics={"f1": 0.9})

            # Re-create manager with same base dir
            manager2 = ModelVersionManager(base_dir=tmpdir)
            assert len(manager2.list_versions()) == 1
            assert manager2.get_version("v1").metrics["f1"] == 0.9

    def test_activate_version_requires_loader(self):
        """Verify error when activating without a loader set."""
        from src.models.versioning import ModelVersionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelVersionManager(base_dir=tmpdir)
            manager.register_version("v1", "/fake/path/v1")
            with pytest.raises(RuntimeError, match="Model loader not set"):
                manager.activate_version("v1")

    def test_activate_version_file_not_found(self):
        """Verify error when model path doesn't exist."""
        from src.models.versioning import ModelVersionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelVersionManager(base_dir=tmpdir)
            manager.set_loader(lambda path: "dummy_model")
            manager.register_version("v1", "/nonexistent/path/v1")
            with pytest.raises(FileNotFoundError):
                manager.activate_version("v1")

    def test_activate_version_loader_failure(self):
        """Verify that loader failure doesn't corrupt active state."""
        from src.models.versioning import ModelVersionManager
        import threading

        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = os.path.join(tmpdir, "models", "v1")
            os.makedirs(model_dir)
            marker = os.path.join(model_dir, "model.bin")
            with open(marker, "w") as f:
                f.write("data")

            manager = ModelVersionManager(base_dir=tmpdir)

            # First successful load
            manager.set_loader(lambda path: "model_v1_ok")
            manager.register_version("v1", model_dir)
            success = manager.activate_version("v1")
            assert success
            assert manager.get_active_model() == "model_v1_ok"

            # Now register v2 but loader will fail
            v2_dir = os.path.join(tmpdir, "models", "v2")
            os.makedirs(v2_dir)

            call_count = [0]

            def failing_loader(path):
                call_count[0] += 1
                if "v2" in path:
                    raise RuntimeError("Failed to load v2")
                return "model_v1_ok"

            manager.set_loader(failing_loader)
            manager.register_version("v2", v2_dir)
            success = manager.activate_version("v2")
            assert not success  # activation should fail

            # Active model should still be v1
            assert manager.get_active_model() == "model_v1_ok"

    def test_atomic_swap_race_safety(self):
        """Concurrent activate/get_active_model should not deadlock or return None."""
        from src.models.versioning import ModelVersionManager
        import concurrent.futures

        with tempfile.TemporaryDirectory() as tmpdir:
            model_a = os.path.join(tmpdir, "models", "v1")
            model_b = os.path.join(tmpdir, "models", "v2")
            os.makedirs(model_a)
            os.makedirs(model_b)
            with open(os.path.join(model_a, "model.bin"), "w") as f:
                f.write("a")
            with open(os.path.join(model_b, "model.bin"), "w") as f:
                f.write("b")

            manager = ModelVersionManager(base_dir=tmpdir)

            def loader(path):
                if "v1" in path:
                    return "model_a"
                return "model_b"

            manager.set_loader(loader)
            manager.register_version("v1", model_a)
            manager.register_version("v2", model_b)
            manager.activate_version("v1")

            results = []

            def read_loop():
                for _ in range(100):
                    model = manager.get_active_model()
                    results.append(model)

            def swap_loop():
                for _ in range(50):
                    manager.activate_version("v2")
                    manager.activate_version("v1")

            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
                ex.submit(swap_loop)
                ex.submit(read_loop)
                ex.submit(read_loop)

            # All reads should return a valid model (never None)
            assert all(r is not None for r in results)
            assert all(r in ("model_a", "model_b") for r in results)

    def test_metrics_summary(self):
        """Verify metrics summary output structure."""
        from src.models.versioning import ModelVersionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ModelVersionManager(base_dir=tmpdir)
            manager.register_version("v1", "/fake/path/v1", metrics={"acc": 0.85})

            summary = manager.get_metrics_summary()
            assert "active_version" in summary
            assert "total_versions" in summary
            assert summary["total_versions"] == 1


class TestModelVersion:
    def test_model_version_dataclass(self):
        """Verify ModelVersion dataclass fields."""
        from src.models.versioning import ModelVersion
        v = ModelVersion(
            version_id="v1",
            path="/path/to/model",
            created_at=1000.0,
            metrics={"accuracy": 0.9},
            is_quantized=True,
            model_type="bert-onnx",
        )
        assert v.version_id == "v1"
        assert v.path == "/path/to/model"
        assert v.metrics["accuracy"] == 0.9
        assert v.is_quantized is True

    def test_model_version_defaults(self):
        """Verify ModelVersion defaults."""
        from src.models.versioning import ModelVersion
        v = ModelVersion(version_id="v1", path="/path")
        assert v.created_at == 0.0
        assert v.metrics == {}
        assert v.is_quantized is False
        assert v.model_type == "bert"
