import importlib


def test_legal_ai_package_is_importable() -> None:
    importlib.import_module("legal_ai")
