"""Data augmentation for Chinese review text."""
import random
import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Built-in synonym dictionary for Chinese review domain
_SYNONYM_DICT = {
    # Quality
    "质量": "品质",
    "品质": "质量",
    "做工": "工艺",
    "材质": "材料",
    "手感": "触感",
    "耐用": "耐穿",
    # Logistics
    "物流": "配送",
    "配送": "物流",
    "快递": "速递",
    "送货": "发货",
    "发货": "送货",
    "包装": "包裝",
    # Service
    "客服": "售后",
    "售后": "客服",
    "态度": "服务",
    # Price
    "价格": "价钱",
    "划算": "合算",
    "便宜": "实惠",
    "实惠": "便宜",
    "优惠": "折扣",
    "折扣": "优惠",
    # Sentiment
    "好": "棒",
    "棒": "好",
    "差": "烂",
    "烂": "差",
    "喜欢": "喜爱",
    "满意": "满意",
    "推荐": "推荐",
    # Common
    "非常": "十分",
    "十分": "非常",
    "很": "挺",
    "挺": "很",
    "特别": "尤其",
    "有点": "有些",
    "比较": "相对",
    "真的": "的确",
    "确实": "的确",
    "完全": "彻底",
    "马上": "立刻",
    "一直": "始终",
}


def _get_synonyms(word: str) -> list[str]:
    """Get synonyms for a word from the built-in dictionary."""
    return [_SYNONYM_DICT[word]] if word in _SYNONYM_DICT else []


def random_mask(text: str, mask_prob: float = 0.1, mask_token: str = "[MASK]") -> str:
    """Randomly mask characters in text (character-level)."""
    chars = list(text)
    for i in range(len(chars)):
        if random.random() < mask_prob:
            chars[i] = mask_token
    return "".join(chars)


def synonym_replace(text: str, replace_prob: float = 0.15) -> str:
    """Replace words with synonyms using a built-in dictionary.

    Uses jieba for word segmentation and a domain-specific synonym map.
    """
    import jieba

    words = jieba.lcut(text)
    result = []
    replaced = False
    for word in words:
        if len(word) >= 2 and random.random() < replace_prob:
            synonyms = _get_synonyms(word)
            if synonyms:
                result.append(random.choice(synonyms))
                replaced = True
                continue
        result.append(word)
    output = "".join(result)
    return output if replaced else text


def random_swap(text: str, swap_prob: float = 0.05) -> str:
    """Randomly swap adjacent characters."""
    chars = list(text)
    for i in range(len(chars) - 1):
        if random.random() < swap_prob:
            chars[i], chars[i + 1] = chars[i + 1], chars[i]
    return "".join(chars)


def back_translate(text: str, source_lang: str = "zh", target_lang: str = "en") -> str:
    """Back-translation augmentation using a translation API.

    Translates text to target language and back to source.
    NOTE: Requires translation API keys configured via environment variables.

    Supported backends:
      - "dummy": Returns original text unchanged (fallback when no API configured)
      - "baidu": Baidu Translate API (BAIDU_APP_ID, BAIDU_SECRET_KEY env vars)

    Args:
        text: Input text to augment.
        source_lang: Source language code (default: "zh").
        target_lang: Intermediate language code (default: "en").

    Returns:
        Back-translated text, or original text if no API configured.
    """
    import os

    # Baidu Translate API
    app_id = os.getenv("BAIDU_APP_ID")
    secret_key = os.getenv("BAIDU_SECRET_KEY")
    if app_id and secret_key:
        try:
            from baidu_translate import Translator

            translator = Translator(app_id, secret_key)
            intermediate = translator.translate(text, from_lang=source_lang, to=target_lang)
            result = translator.translate(intermediate, from_lang=target_lang, to=source_lang)
            if result and result != text:
                return result
        except Exception as e:
            logger.warning("Back-translation failed: %s", e)

    logger.info("No translation API configured, returning original text")
    return text


def augment_text(text: str, num_augmented: int = 2) -> list[str]:
    """Generate augmented versions of input text.

    Applies a random sequence of augmentation operations to produce diverse outputs.
    Operations: random_mask, synonym_replace, random_swap.

    Returns:
        List containing original text plus augmented variants.
    """
    augmented = [text]
    ops = [random_mask, synonym_replace, random_swap]
    for _ in range(num_augmented):
        op = random.choice(ops)
        augmented.append(op(text))
    return augmented


def augment_dataset(
    df,
    text_column: str = "content",
    label_column: str = "label",
    num_augmented: int = 2,
    max_per_class: Optional[int] = None,
) -> "pd.DataFrame":
    """Augment a pandas DataFrame by generating variants of each row.

    Args:
        df: Input DataFrame with text and label columns.
        text_column: Name of the text column to augment.
        label_column: Name of the label column (preserved as-is).
        num_augmented: Number of augmented variants per original row.
        max_per_class: Maximum rows per class after augmentation (None = unlimited).

    Returns:
        New DataFrame with original + augmented rows.
    """
    import pandas as pd

    rows = []
    for _, row in df.iterrows():
        rows.append(row.to_dict())
        text = row.get(text_column, "")
        if not isinstance(text, str) or not text.strip():
            continue
        augmented_texts = augment_text(text, num_augmented)
        for aug_text in augmented_texts[1:]:
            new_row = row.to_dict()
            new_row[text_column] = aug_text
            rows.append(new_row)

    result = pd.DataFrame(rows)

    # Balance by class if max_per_class is set
    if max_per_class is not None and label_column in result.columns:
        groups = []
        for label in result[label_column].unique():
            group = result[result[label_column] == label]
            if len(group) > max_per_class:
                group = group.sample(n=max_per_class, random_state=42)
            groups.append(group)
        result = pd.concat(groups, ignore_index=True)

    return result
