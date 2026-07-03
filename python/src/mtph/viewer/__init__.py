"""mtph.viewer — the local reader server behind ``mtph view``."""
from .server import make_server

__all__ = ["make_server"]
