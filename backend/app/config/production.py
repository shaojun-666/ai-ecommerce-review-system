from .default import DefaultConfig


class ProductionConfig(DefaultConfig):
    DEBUG = False
    SQLALCHEMY_ECHO = False
    LOG_LEVEL = "WARNING"
