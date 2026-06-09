from .default import DefaultConfig


class DevelopmentConfig(DefaultConfig):
    DEBUG = True
    SQLALCHEMY_ECHO = True
    LOG_LEVEL = "DEBUG"
