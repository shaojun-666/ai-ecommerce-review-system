# Heavy modules loaded lazily to avoid eager torch import
from src.models.bert.config import BERTConfig, LoRAConfig


def BERTPredictor(*args, **kwargs):
    from src.models.bert.model import BERTPredictor as _cls
    return _cls(*args, **kwargs)


def BERTONNXPredictor(*args, **kwargs):
    from src.models.bert.model import BERTONNXPredictor as _cls
    return _cls(*args, **kwargs)


__all__ = ["BERTPredictor", "BERTONNXPredictor", "BERTConfig", "LoRAConfig"]
