# Heavy modules loaded lazily


def Evaluator(*args, **kwargs):
    from src.training.evaluator import Evaluator as _cls
    return _cls(*args, **kwargs)


def optimizer():
    from src.training import optimizer as _mod
    return _mod


__all__ = ["Evaluator", "optimizer"]
