"""Utility functions for BERT model operations."""
import os
import json
import logging
from typing import Optional

import torch
import numpy as np

logger = logging.getLogger(__name__)


def set_seed(seed: int = 42):
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def get_device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


def save_model(model, tokenizer, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    model.save_pretrained(output_dir)
    if tokenizer:
        tokenizer.save_pretrained(output_dir)
    logger.info("Model saved to %s", output_dir)


def export_to_onnx(model, tokenizer, output_dir: str, max_length: int = 128):
    import torch.onnx
    os.makedirs(output_dir, exist_ok=True)

    dummy_input = tokenizer(
        "测试输入", return_tensors="pt", max_length=max_length, padding="max_length", truncation=True
    )
    torch.onnx.export(
        model,
        tuple(dummy_input.values()),
        os.path.join(output_dir, "model.onnx"),
        input_names=["input_ids", "attention_mask"],
        output_names=["logits"],
        dynamic_axes={
            "input_ids": {0: "batch_size", 1: "sequence_length"},
            "attention_mask": {0: "batch_size", 1: "sequence_length"},
            "logits": {0: "batch_size"},
        },
        opset_version=14,
    )
    logger.info("ONNX model exported to %s", output_dir)


def count_parameters(model) -> dict:
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    return {"total": total, "trainable": trainable, "frozen": total - trainable}
