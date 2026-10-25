"""Smoke: models demo assertions still pass on SQLite."""

from app.models import _demo


def test_models_demo():
    _demo()
