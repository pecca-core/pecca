import pytest
import yaml

from pecca.config import apply as apply_mod
from pecca.config import loader
from pecca.config.resolve import deep_merge, find_vars, resolve_extends, substitute
from pecca.connectors.secrets.env import EnvSecrets
from pecca.core.errors import ConfigError, GovernanceError

BASE = {
    "version": 1,
    "workspace": {"name": "prod"},
    "projects": {"p": {"governance": {"extends": "default"}}},
}


def test_extends_builtin_and_override():
    gov = resolve_extends(
        {"extends": "default", "transitions": {"shadow->live": {"gates": ["agreement >= 0.95"]}}}
    )
    t = gov["transitions"]["shadow->live"]
    assert t["gates"] == ["agreement >= 0.95"]  # lists are replaced
    assert t["approvals"]["groups"] == ["ml-leads"]  # dicts are merged
    assert gov["retention"]["evidence"] == "3y"


def test_extends_chain_and_path(tmp_path):
    (tmp_path / "base.yaml").write_text(
        "governance:\n  extends: none\n  retention: {evidence: 9y}\n"
    )
    gov = resolve_extends({"extends": str(tmp_path / "base.yaml")})
    assert gov["retention"]["evidence"] == "9y" and "record->shadow" in gov["transitions"]


def test_unknown_profile():
    with pytest.raises(ConfigError, match="unknown governance profile"):
        resolve_extends({"extends": "nope"})


def test_all_profiles_valid_and_have_disclaimer():
    from pecca.config.resolve import profiles_dir

    for f in profiles_dir().glob("*.yaml"):
        assert f.read_text().startswith(
            "# TEMPLATE ONLY. This file is a convenience preset and is NOT legal or regulatory advice."
        )
        loader.validate_governance(resolve_extends({"extends": f.stem}))
    names = {f.stem for f in profiles_dir().glob("*.yaml")}
    assert names == {"none", "default", "sr11-7", "eu-ai-act", "cbuae", "bsp", "rbi", "sarb"}
    eu = resolve_extends({"extends": "eu-ai-act"})
    assert "human_oversight_log" in eu["transitions"]["shadow->live"]["evidence"]


def test_schema_rejects_bad_config():
    with pytest.raises(ConfigError):
        loader.resolve({"version": 2})
    with pytest.raises(ConfigError, match="gates|items"):
        loader.resolve(
            {
                "version": 1,
                "projects": {
                    "p": {"governance": {"transitions": {"shadow->live": {"gates": [5]}}}}
                },
            }
        )
    with pytest.raises(ConfigError):
        loader.resolve(
            {
                "version": 1,
                "projects": {"p": {"governance": {"retention": {"evidence": "forever"}}}},
            }
        )


def test_vars():
    assert find_vars({"a": "x ${FOO} y", "b": ["${BAR}"]}) == {"FOO", "BAR"}

    class S(EnvSecrets): ...

    import os

    os.environ["FOO"] = "1"
    try:
        assert substitute({"a": "x-${FOO}"}, S()) == {"a": "x-1"}
    finally:
        del os.environ["FOO"]
    with pytest.raises(Exception, match="BAR_MISSING"):
        substitute("${BAR_MISSING}", EnvSecrets())


def test_apply_errors_on_unresolved_and_never_stores_secrets(tmp_path, monkeypatch):
    cfg = {
        **BASE,
        "projects": {
            "p": {
                "governance": {"extends": "none"},
                "integrations": {"notifier": {"type": "slack", "webhook": "${SLACK_WEBHOOK}"}},
            }
        },
    }
    f = tmp_path / "pecca.yaml"
    f.write_text(yaml.safe_dump(cfg))
    monkeypatch.delenv("SLACK_WEBHOOK", raising=False)
    with pytest.raises(ConfigError, match="SLACK_WEBHOOK"):
        apply_mod.apply(f)
    monkeypatch.setenv("SLACK_WEBHOOK", "https://hooks.example/secret-value")
    diff, resolved = apply_mod.apply(f)
    stored = (tmp_path / ".pecca" / "config.resolved.yaml").read_text()
    assert "${SLACK_WEBHOOK}" in stored and "secret-value" not in stored
    assert "+" in diff
    diff2, _ = apply_mod.apply(f)
    assert diff2 == ""  # idempotent


def test_apply_rejects_bad_gate(tmp_path):
    cfg = {
        "version": 1,
        "projects": {
            "p": {
                "governance": {
                    "extends": "none",
                    "transitions": {"shadow->live": {"gates": ["__import__('os') > 1"]}},
                }
            }
        },
    }
    f = tmp_path / "pecca.yaml"
    f.write_text(yaml.safe_dump(cfg))
    with pytest.raises(GovernanceError):
        apply_mod.apply(f)


def test_deep_merge_is_nondestructive():
    a = {"x": {"y": [1]}}
    b = deep_merge(a, {"x": {"z": 2}})
    assert a == {"x": {"y": [1]}} and b == {"x": {"y": [1], "z": 2}}
