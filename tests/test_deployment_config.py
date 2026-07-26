import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_vercel_configuration_keeps_fastapi_runtime_constrained() -> None:
    config = json.loads((PROJECT_ROOT / "vercel.json").read_text(encoding="utf-8"))

    assert config["framework"] == "fastapi"
    assert config["fluid"] is True
    assert config["functions"]["app/main.py"]["maxDuration"] == 30


def test_vercel_upload_allowlist_excludes_non_runtime_directories() -> None:
    ignore_rules = (PROJECT_ROOT / ".vercelignore").read_text(encoding="utf-8")

    assert "!/.python-version" in ignore_rules
    assert "!/pyproject.toml" in ignore_rules
    assert "!/uv.lock" in ignore_rules
    assert "!/vercel.json" in ignore_rules
    assert "!/app/**/*.py" in ignore_rules
    assert "tests/" not in ignore_rules
    assert "docs/" not in ignore_rules
    assert "supabase/" not in ignore_rules


def test_ci_uses_locked_dependencies_without_a_tool_cache() -> None:
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert "astral-sh/setup-uv@v6" in workflow
    assert 'python-version: "3.12"' in workflow
    assert "enable-cache: false" in workflow
    assert "uv sync --locked --dev" in workflow
    assert (
        'uv run pytest -m "not integration" --cov=app --cov-report=term-missing'
        in workflow
    )


def test_runbook_keeps_license_deployment_boundaries_explicit() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    assert "`license` Supabase schema" in readme
    assert "fastapi-license" in readme
    assert "vercel deploy --target=preview" in readme
    assert "`--prebuilt`는 사용하지 않습니다" in readme
    assert "`--prod`" in readme
    assert "vercel rollback <deployment-url-or-id>" in readme
