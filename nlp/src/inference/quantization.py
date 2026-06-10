"""ONNX export and INT8 quantization utilities."""
import os
import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


def export_to_onnx(
    model,
    tokenizer,
    output_dir: str,
    max_length: int = 128,
    opset_version: int = 14,
) -> str:
    """Export a HuggingFace BERT model to ONNX format.

    Args:
        model: HuggingFace BertForSequenceClassification model.
        tokenizer: HuggingFace BertTokenizer.
        output_dir: Directory to save the ONNX model.
        max_length: Maximum sequence length for the dummy input.
        opset_version: ONNX opset version (14 supports most optimizations).

    Returns:
        Path to the exported ONNX file.
    """
    import torch

    os.makedirs(output_dir, exist_ok=True)
    onnx_path = os.path.join(output_dir, "model.onnx")

    model.eval()
    dummy_input = tokenizer(
        "测试输入",
        return_tensors="pt",
        max_length=max_length,
        padding="max_length",
        truncation=True,
    )

    torch.onnx.export(
        model,
        tuple(dummy_input.values()),
        onnx_path,
        input_names=["input_ids", "attention_mask"],
        output_names=["logits"],
        dynamic_axes={
            "input_ids": {0: "batch_size", 1: "sequence_length"},
            "attention_mask": {0: "batch_size", 1: "sequence_length"},
            "logits": {0: "batch_size"},
        },
        opset_version=opset_version,
        do_constant_folding=True,
    )

    logger.info("ONNX model exported to %s", onnx_path)
    return onnx_path


def quantize_onnx_int8(
    onnx_path: str,
    output_path: Optional[str] = None,
    calibration_data: Optional[list[str]] = None,
    tokenizer=None,
    max_length: int = 128,
) -> str:
    """Quantize an ONNX model to INT8 using dynamic quantization.

    Uses ONNX Runtime's dynamic quantization (INT8 for weights, FP32 for activations).
    This is a calibration-free approach that works well for transformer models.

    Args:
        onnx_path: Path to the FP32 ONNX model.
        output_path: Path for the quantized model. If None, uses {onnx_path}.int8.onnx.
        calibration_data: Optional list of text samples for calibration.
                          If None, uses built-in default samples.
        tokenizer: Tokenizer for processing calibration data (required if calibration_data used).
        max_length: Max sequence length for calibration.

    Returns:
        Path to the quantized ONNX model.
    """
    import onnx
    from onnxruntime.quantization import quantize_dynamic, QuantType

    if output_path is None:
        output_path = onnx_path + ".int8.onnx"

    # If calibration data provided, do QDQ quantization for better accuracy
    # Otherwise, fall back to dynamic quantization
    if calibration_data and tokenizer:
        _calibrate_and_quantize(onnx_path, output_path, calibration_data, tokenizer, max_length)
    else:
        quantize_dynamic(
            model_input=onnx_path,
            model_output=output_path,
            weight_type=QuantType.QInt8,
            per_channel=True,
            reduce_range=False,
        )

    # Verify the quantized model
    model = onnx.load(output_path)
    onnx.checker.check_model(model)

    original_size = os.path.getsize(onnx_path)
    quantized_size = os.path.getsize(output_path)
    logger.info(
        "INT8 quantization complete: %s (%.1f MB → %.1f MB, %.1f%% reduction)",
        output_path,
        original_size / 1e6,
        quantized_size / 1e6,
        (1 - quantized_size / original_size) * 100,
    )

    return output_path


def _calibrate_and_quantize(
    onnx_path: str,
    output_path: str,
    calibration_data: list[str],
    tokenizer,
    max_length: int,
):
    """QDQ (Quantization-DataQuantization) calibration-based quantization.

    Uses calibration data to determine optimal quantization ranges,
    typically yields better accuracy than pure dynamic quantization.
    """
    import onnx
    from onnxruntime.quantization import quantize_static, CalibrationMethod
    from onnxruntime.quantization.qdq_quantizer import QuantFormat
    from onnxruntime.quantization.calibrate import CalibrationDataReader

    class _ReviewCalibrationReader(CalibrationDataReader):
        def __init__(self, texts, tokenizer, max_len):
            self.data = [
                tokenizer(
                    t, return_tensors="np", max_length=max_len,
                    padding="max_length", truncation=True,
                )
                for t in texts
            ]
            self.iter = iter(self.data)
            self.input_names = ["input_ids", "attention_mask"]

        def get_next(self):
            try:
                batch = next(self.iter)
                return {k: batch[k] for k in self.input_names if k in batch}
            except StopIteration:
                return None

    try:
        dr = _ReviewCalibrationReader(calibration_data, tokenizer, max_length)
        quantize_static(
            model_input=onnx_path,
            model_output=output_path,
            calibration_data_reader=dr,
            quant_format=QuantFormat.QDQ,
            per_channel=True,
            activation_type=onnx.onnx_ml_pb2.TensorProto.UINT8,
            weight_type=onnx.onnx_ml_pb2.TensorProto.INT8,
            calibrate_method=CalibrationMethod.MinMax,
            extra_options={"CalibStridedMinMax": True},
        )
    except Exception as e:
        logger.warning("Static quantization failed (%s), falling back to dynamic", e)
        from onnxruntime.quantization import quantize_dynamic, QuantType
        quantize_dynamic(
            model_input=onnx_path,
            model_output=output_path,
            weight_type=QuantType.QInt8,
        )


def benchmark_onnx(
    onnx_path: str,
    tokenizer,
    texts: list[str],
    n_warmup: int = 10,
    n_runs: int = 100,
) -> dict:
    """Benchmark ONNX model inference performance.

    Args:
        onnx_path: Path to ONNX model file.
        tokenizer: HuggingFace tokenizer.
        texts: List of text samples to benchmark with.
        n_warmup: Number of warmup runs before measurement.
        n_runs: Number of timed runs.

    Returns:
        Dict with latency statistics (mean, p50, p95, p99 in ms).
    """
    import onnxruntime as ort
    import time

    session = ort.InferenceSession(
        onnx_path,
        providers=["CPUExecutionProvider"],
    )
    input_names = [inp.name for inp in session.get_inputs()]

    # Pre-tokenize
    inputs = tokenizer(
        texts,
        return_tensors="np",
        truncation=True,
        max_length=128,
        padding=True,
    )
    ort_inputs = {name: inputs[name] for name in input_names if name in inputs}

    # Warmup
    for _ in range(n_warmup):
        session.run(None, ort_inputs)

    # Benchmark
    latencies = []
    for _ in range(n_runs):
        start = time.perf_counter()
        session.run(None, ort_inputs)
        latencies.append((time.perf_counter() - start) * 1000)  # ms

    latencies.sort()
    return {
        "model": os.path.basename(onnx_path),
        "batch_size": len(texts),
        "n_runs": n_runs,
        "mean_ms": float(np.mean(latencies)),
        "p50_ms": float(np.median(latencies)),
        "p95_ms": float(latencies[int(len(latencies) * 0.95)]),
        "p99_ms": float(latencies[int(len(latencies) * 0.99)]),
        "min_ms": float(latencies[0]),
        "max_ms": float(latencies[-1]),
    }


def accuracy_comparison(
    pytorch_model,
    onnx_session,
    tokenizer,
    test_texts: list[str],
    labels: Optional[list[int]] = None,
) -> dict:
    """Compare accuracy between PyTorch and ONNX models.

    Args:
        pytorch_model: HuggingFace BERT model (evaluated first).
        onnx_session: ONNX Runtime InferenceSession.
        tokenizer: BertTokenizer.
        test_texts: List of test text samples.
        labels: Optional ground truth labels for accuracy comparison.

    Returns:
        Dict with comparison results and prediction agreement rate.
    """
    import torch
    import onnxruntime as ort

    input_names = [inp.name for inp in onnx_session.get_inputs()]

    inputs = tokenizer(
        test_texts,
        return_tensors="pt",
        truncation=True,
        max_length=128,
        padding=True,
    )

    # PyTorch predictions
    pytorch_model.eval()
    with torch.no_grad():
        pt_outputs = pytorch_model(**inputs)
        pt_preds = torch.argmax(pt_outputs.logits, dim=-1).numpy()

    # ONNX predictions
    ort_inputs = {name: inputs[name].numpy() for name in input_names if name in inputs}
    ort_outputs = onnx_session.run(None, ort_inputs)
    ort_preds = np.argmax(ort_outputs[0], axis=-1)

    # Agreement
    agreement = (pt_preds == ort_preds).mean()
    result = {
        "agreement_rate": float(agreement),
        "total_samples": len(test_texts),
    }

    if labels is not None:
        pt_acc = (pt_preds == np.array(labels)).mean()
        ort_acc = (ort_preds == np.array(labels)).mean()
        result["pt_accuracy"] = float(pt_acc)
        result["ort_accuracy"] = float(ort_acc)
        result["accuracy_delta"] = float(ort_acc - pt_acc)

    return result
