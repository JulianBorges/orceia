# conftest.py — Configuração global do pytest para o backend OrceIA V3
import pytest


def pytest_configure(config):
    """Registra markers customizados."""
    config.addinivalue_line("markers", "asyncio: marca testes assíncronos")
