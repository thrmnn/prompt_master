"""Shared test fixtures."""

import pytest
from click.testing import CliRunner


@pytest.fixture
def cli_runner():
    return CliRunner()


@pytest.fixture
def tmp_template_dir(tmp_path):
    """Create a temp directory with a test template."""
    template = tmp_path / "test.toml"
    template.write_text(
        '[meta]\nname = "test"\ndescription = "Test template"\n\n'
        '[role]\ndefault = "You are a test assistant."\n\n'
        "[defaults]\n"
        'format = "Test format."\n'
    )
    return tmp_path


@pytest.fixture
def mock_client(mocker):
    """Mock ClaudeClient to avoid real API calls."""
    mock = mocker.patch("prompt_master.optimizer.ClaudeClient")
    instance = mock.return_value
    instance.generate.return_value = (
        "# Role\nYou are an expert assistant.\n\n"
        "# Task\nDo the thing the user asked for.\n\n"
        "# Output Format\nProvide a clear response."
    )
    return instance
