"""Tests for INT8 quantization functionality."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


@pytest.mark.skipif(
    not os.environ.get("TEST_ONNX"),
    reason="ONNX quantization tests require TEST_ONNX env var and full stack",
)
class TestQuantization:
    def test_quantize_dynamic_reduces_size(self, tmp_path):
        """Verify INT8 quantization reduces model size."""
        import torch
        from transformers import BertTokenizer, BertForSequenceClassification
        from src.inference.quantization import export_to_onnx, quantize_onnx_int8

        tokenizer = BertTokenizer.from_pretrained("bert-base-chinese")
        model = BertForSequenceClassification.from_pretrained("bert-base-chinese", num_labels=3)

        onnx_path = export_to_onnx(model, tokenizer, str(tmp_path))
        quant_path = quantize_onnx_int8(onnx_path, output_dir=str(tmp_path))

        fp32_size = os.path.getsize(onnx_path)
        int8_size = os.path.getsize(quant_path)
        assert int8_size < fp32_size, "INT8 model should be smaller than FP32"

    def test_quantized_model_runs_inference(self, tmp_path):
        """Verify quantized model produces valid outputs."""
        import numpy as np
        import onnxruntime as ort
        from transformers import BertTokenizer, BertForSequenceClassification
        from src.inference.quantization import export_to_onnx, quantize_onnx_int8

        tokenizer = BertTokenizer.from_pretrained("bert-base-chinese")
        model = BertForSequenceClassification.from_pretrained("bert-base-chinese", num_labels=3)

        onnx_path = export_to_onnx(model, tokenizer, str(tmp_path))
        quant_path = quantize_onnx_int8(onnx_path, output_dir=str(tmp_path))

        session = ort.InferenceSession(quant_path, providers=["CPUExecutionProvider"])
        inputs = tokenizer("产品很好", return_tensors="np", truncation=True, padding=True, max_length=128)
        input_names = [inp.name for inp in session.get_inputs()]
        ort_inputs = {name: inputs[name] for name in input_names if name in inputs}
        outputs = session.run(None, ort_inputs)
        assert outputs[0].shape[1] == 3  # 3 classes

    def test_accuracy_loss_within_threshold(self, tmp_path):
        """Verify accuracy loss from INT8 quantization is under 2%.

        This test requires test data with labels to compute accuracy.
        Uses relative agreement as proxy when labels aren't available.
        """
        import torch
        import numpy as np
        from transformers import BertTokenizer, BertForSequenceClassification
        import onnxruntime as ort
        from src.inference.quantization import export_to_onnx, quantize_onnx_int8, accuracy_comparison

        tokenizer = BertTokenizer.from_pretrained("bert-base-chinese")
        model = BertForSequenceClassification.from_pretrained("bert-base-chinese", num_labels=3)
        model.eval()

        onnx_path = export_to_onnx(model, tokenizer, str(tmp_path))
        quant_path = quantize_onnx_int8(onnx_path, output_dir=str(tmp_path))

        # Compare FP32 ONNX vs INT8 ONNX
        fp32_session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
        int8_session = ort.InferenceSession(quant_path, providers=["CPUExecutionProvider"])

        test_texts = [
            "这个产品质量非常好物流也很快",
            "差评东西质量太差了",
            "一般般吧没有想象中好",
            "客服态度很好解决问题很快",
            "价格便宜性价比很高推荐购买",
            "收到货很满意包装完好",
            "不太满意用了一周就坏了",
            "还行吧凑合能用",
            "物流太慢了等了好几天",
            "非常喜欢这个产品做工精细",
        ] * 5  # 50 samples for stable measurement

        inputs = tokenizer(test_texts, return_tensors="np", truncation=True, padding=True, max_length=128)
        input_names = [inp.name for inp in fp32_session.get_inputs()]
        ort_inputs = {name: inputs[name] for name in input_names if name in inputs}

        fp32_outputs = fp32_session.run(None, ort_inputs)
        int8_outputs = int8_session.run(None, ort_inputs)

        fp32_preds = np.argmax(fp32_outputs[0], axis=-1)
        int8_preds = np.argmax(int8_outputs[0], axis=-1)

        agreement = (fp32_preds == int8_preds).mean()
        assert agreement >= 0.98, (
            f"INT8 quantization changed predictions in {(1-agreement)*100:.1f}% of cases "
            f"(threshold: 2%)"
        )

    def test_quantize_with_calibration_data(self, tmp_path):
        """Verify calibration-based quantization works."""
        import torch
        from transformers import BertTokenizer, BertForSequenceClassification
        from src.inference.quantization import export_to_onnx, quantize_onnx_int8

        tokenizer = BertTokenizer.from_pretrained("bert-base-chinese")
        model = BertForSequenceClassification.from_pretrained("bert-base-chinese", num_labels=3)

        onnx_path = export_to_onnx(model, tokenizer, str(tmp_path))
        calib_texts = ["好产品", "差评", "一般", "非常满意", "不太好"] * 10
        quant_path = quantize_onnx_int8(
            onnx_path,
            output_dir=str(tmp_path),
            calibration_data=calib_texts,
            tokenizer=tokenizer,
        )
        assert os.path.exists(quant_path)

    def test_benchmark_quantized_vs_fp32(self, tmp_path):
        """Benchmark INT8 vs FP32 latency."""
        import torch
        from transformers import BertTokenizer, BertForSequenceClassification
        import onnxruntime as ort
        from src.inference.quantization import export_to_onnx, quantize_onnx_int8, benchmark_onnx

        tokenizer = BertTokenizer.from_pretrained("bert-base-chinese")
        model = BertForSequenceClassification.from_pretrained("bert-base-chinese", num_labels=3)

        onnx_path = export_to_onnx(model, tokenizer, str(tmp_path))
        quant_path = quantize_onnx_int8(onnx_path, output_dir=str(tmp_path))

        texts = ["这个产品非常好用"] * 4
        fp32_result = benchmark_onnx(onnx_path, tokenizer, texts, n_warmup=2, n_runs=10)
        int8_result = benchmark_onnx(quant_path, tokenizer, texts, n_warmup=2, n_runs=10)

        assert int8_result["mean_ms"] > 0
        assert fp32_result["mean_ms"] > 0
