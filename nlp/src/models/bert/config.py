"""BERT model configuration parameters."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BERTConfig:
    model_name: str = "bert-base-chinese"
    num_labels: int = 3
    num_aspects: int = 4
    max_length: int = 128
    hidden_dropout: float = 0.3
    attention_dropout: float = 0.3
    learning_rate: float = 2e-5
    batch_size: int = 32
    epochs: int = 5
    warmup_ratio: float = 0.1
    weight_decay: float = 0.01
    max_grad_norm: float = 1.0
    early_stopping_patience: int = 3
    fp16: bool = True
    output_dir: str = "./models/bert-sentiment"
    save_total_limit: int = 2
    seed: int = 42

    label_map: tuple = ("negative", "neutral", "positive")
    aspect_labels: tuple = ("quality", "logistics", "service", "price")


@dataclass
class LoRAConfig:
    r: int = 8
    alpha: int = 16
    dropout: float = 0.1
    target_modules: tuple = ("q_proj", "k_proj", "v_proj", "o_proj")
    bias: str = "none"
    task_type: str = "SEQ_CLS"
