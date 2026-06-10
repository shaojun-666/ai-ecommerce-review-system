"""Tests for ONNX export functionality."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


@pytest.mark.skipif(
    not os.environ.get("TEST_ONNX"),
    reason="ONNX tests require TEST_ONNX env var and GPU/transformers available",
)
class TestONNXExport:
    def test_export_to_onnx(self, tmp_path):
        """Verify ONNX export produces valid model file."""
        import torch
        from transformers import BertTokenizer, BertForSequenceClassification
        from src.inference.quantization import export_to_onnx

        tokenizer = BertTokenizer.from_pretrained("bert-base-chinese")
        model = BertForSequenceClassification.from_pretrained("bert-base-chinese", num_labels=3)

        onnx_path = export_to_onnx(model, tokenizer, str(tmp_path))
        assert os.path.exists(onnx_path)

        import onnx
        onnx_model = onnx.load(onnx_path)
        onnx.checker.check_model(onnx_model)

    def test_onnx_output_matches_pytorch(self, tmp_path):
        """Verify ONNX model produces same predictions as PyTorch."""
        import torch
        import numpy as np
        from transformers import BertTokenizer, BertForSequenceClassification
        import onnxruntime as ort
        from src.inference.quantization import export_to_onnx

        tokenizer = BertTokenizer.from_pretrained("bert-base-chinese")
        model = BertForSequenceClassification.from_pretrained("bert-base-chinese", num_labels=3)
        model.eval()

        onnx_path = export_to_onnx(model, tokenizer, str(tmp_path))
        session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])

        texts = ["这个产品非常好用", "质量很差", "一般般吧"]
        inputs = tokenizer(texts, return_tensors="pt", truncation=True, padding=True, max_length=128)

        # PyTorch
        with torch.no_grad():
            pt_outputs = model(**inputs)
        pt_probs = torch.softmax(pt_outputs.logits, dim=-1).numpy()

        # ONNX
        input_names = [inp.name for inp in session.get_inputs()]
        ort_inputs = {name: inputs[name].numpy() for name in input_names if name in inputs}
        ort_outputs = session.run(None, ort_inputs)
        ort_probs = np.exp(ort_outputs[0]) / np.sum(np.exp(ort_outputs[0]), axis=-1, keepdims=True)

        # Check agreement (allow small numerical differences)
        for pt, ort in zip(pt_probs, ort_probs):
            assert np.allclose(pt, ort, atol=1e-4), "ONNX output diverges from PyTorch"

    def test_export_with_dynamic_axes(self, tmp_path):
        """Verify dynamic batch/sequence axes work."""
        import torch
        from transformers import BertTokenizer, BertForSequenceClassification
        import onnxruntime as ort
        from src.inference.quantization import export_to_onnx

        tokenizer = BertTokenizer.from_pretrained("bert-base-chinese")
        model = BertForSequenceClassification.from_pretrained("bert-base-chinese", num_labels=3)

        onnx_path = export_to_onnx(model, tokenizer, str(tmp_path))
        session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])

        # Test with different batch size
        texts_1 = ["好"]
        texts_3 = ["好", "差", "一般"]
        for texts in [texts_1, texts_3]:
            inputs = tokenizer(texts, return_tensors="np", truncation=True, padding=True, max_length=128)
            input_names = [inp.name for inp in session.get_inputs()]
            ort_inputs = {name: inputs[name] for name in input_names if name in inputs}
            outputs = session.run(None, ort_inputs)
            assert outputs[0].shape[0] == len(texts)

    def test_benchmark_returns_expected_keys(self, tmp_path):
        """Verify benchmark utility returns correct structure."""
        import torch
        from transformers import BertTokenizer, BertForSequenceClassification
        from src.inference.quantization import export_to_onnx, benchmark_onnx

        tokenizer = BertTokenizer.from_pretrained("bert-base-chinese")
        model = BertForSequenceClassification.from_pretrained("bert-base-chinese", num_labels=3)
        onnx_path = export_to_onnx(model, tokenizer, str(tmp_path))

        result = benchmark_onnx(onnx_path, tokenizer, ["测试文本"], n_warmup=2, n_runs=5)
        assert "mean_ms" in result
        assert "p50_ms" in result
        assert "p95_ms" in result
        assert result["batch_size"] == 1
        assert result["n_runs"] == 5
