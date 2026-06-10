# Heavy modules loaded lazily


def ErrorAnalyzer(*args, **kwargs):
    from src.evaluation.error_analysis import ErrorAnalyzer as _cls
    return _cls(*args, **kwargs)


__all__ = ["ErrorAnalyzer"]
