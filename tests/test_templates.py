"""Tests for template loading and management."""

import pytest

from prompt_master.templates import (
    TemplateNotFoundError,
    list_templates,
    load_template,
    save_template,
    show_template,
)


def test_load_builtin_template():
    t = load_template("general")
    assert t["meta"]["name"] == "general"
    assert "role" in t


def test_load_all_builtin_templates():
    for name in ["general", "code", "creative", "analysis"]:
        t = load_template(name)
        assert t["meta"]["name"] == name


def test_load_template_by_path(tmp_template_dir):
    path = str(tmp_template_dir / "test.toml")
    t = load_template(path)
    assert t["meta"]["name"] == "test"


def test_load_missing_template():
    with pytest.raises(TemplateNotFoundError):
        load_template("nonexistent_template_xyz")


def test_list_templates():
    templates = list_templates()
    names = [t["name"] for t in templates]
    assert "general" in names
    assert "code" in names


def test_show_template():
    content = show_template("general")
    assert "[meta]" in content
    assert "general" in content


def test_show_missing_template():
    with pytest.raises(TemplateNotFoundError):
        show_template("nonexistent_template_xyz")


def test_save_template(tmp_path, tmp_template_dir, monkeypatch):
    monkeypatch.setattr("prompt_master.templates.USER_TEMPLATE_DIR", tmp_path / "user_templates")
    source = str(tmp_template_dir / "test.toml")
    dest = save_template("my_template", source)
    assert dest.exists()
    assert dest.name == "my_template.toml"


def test_save_template_missing_source(tmp_path):
    with pytest.raises(FileNotFoundError):
        save_template("x", "/nonexistent/file.toml")
