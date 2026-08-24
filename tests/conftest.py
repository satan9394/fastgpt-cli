"""Shared pytest fixtures for fastgpt-cli tests."""

from __future__ import annotations

import pytest
from click.testing import CliRunner


@pytest.fixture()
def runner():
    """CliRunner with mixed stderr disabled, so result.output == stdout only."""
    return CliRunner(mix_stderr=False)
