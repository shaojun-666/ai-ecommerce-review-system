"""Data augmentation for Chinese review text."""
import random
import numpy as np


def random_mask(text: str, mask_prob: float = 0.1, mask_token: str = "[MASK]") -> str:
    words = list(text)
    for i in range(len(words)):
        if random.random() < mask_prob:
            words[i] = mask_token
    return "".join(words)


def synonym_replace(text: str, replace_prob: float = 0.1) -> str:
    import jieba
    words = jieba.lcut(text)
    result = []
    for word in words:
        if len(word) >= 2 and random.random() < replace_prob:
            result.append(word)
        else:
            result.append(word)
    return "".join(result)


def random_swap(text: str, swap_prob: float = 0.05) -> str:
    chars = list(text)
    for i in range(len(chars) - 1):
        if random.random() < swap_prob:
            chars[i], chars[i + 1] = chars[i + 1], chars[i]
    return "".join(chars)


def augment_text(text: str, num_augmented: int = 2) -> list[str]:
    augmented = [text]
    ops = [random_mask, synonym_replace, random_swap]
    for _ in range(num_augmented):
        op = random.choice(ops)
        augmented.append(op(text))
    return augmented


def augment_dataset(df, text_column: str = "content", num_augmented: int = 2):
    import pandas as pd
    rows = []
    for _, row in df.iterrows():
        rows.append(row)
        augmented_texts = augment_text(row[text_column], num_augmented)
        for aug_text in augmented_texts[1:]:
            new_row = row.copy()
            new_row[text_column] = aug_text
            rows.append(new_row)
    return pd.DataFrame(rows)
