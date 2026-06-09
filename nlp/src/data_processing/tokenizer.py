"""BERT tokenizer wrapper with batch support."""
from typing import Optional
from transformers import BertTokenizer


class ReviewTokenizer:
    def __init__(self, model_name: str = "bert-base-chinese", max_length: int = 128):
        self.tokenizer = BertTokenizer.from_pretrained(model_name)
        self.max_length = max_length

    def encode(self, text: str, padding: bool = True) -> dict:
        return self.tokenizer(
            text,
            truncation=True,
            padding=padding,
            max_length=self.max_length,
            return_tensors=None,
        )

    def encode_batch(self, texts: list[str], padding: bool = True) -> dict:
        return self.tokenizer(
            texts,
            truncation=True,
            padding=padding,
            max_length=self.max_length,
            return_tensors=None,
        )

    def encode_pt(self, text: str, padding: bool = True):
        import torch
        result = self.tokenizer(
            text,
            truncation=True,
            padding=padding,
            max_length=self.max_length,
            return_tensors="pt",
        )
        return {k: v.squeeze(0) for k, v in result.items()}

    @property
    def vocab_size(self) -> int:
        return self.tokenizer.vocab_size

    def decode(self, token_ids: list[int]) -> str:
        return self.tokenizer.decode(token_ids, skip_special_tokens=True)
