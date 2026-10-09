import pytest

from strayguard import rules


@pytest.mark.parametrize("path", [
    ".env", ".env.local", "config/.env.production", "server.pem", "tls.key",
    "cert.p12", "id_rsa", "id_ed25519.pub", ".DS_Store", "docs/Thumbs.db",
])
def test_local_only_names(path):
    assert rules.match(path) == "local-only"


@pytest.mark.parametrize("path", [
    ".env.example", ".env.sample", ".env.template",  # T-03
    "src/app.py", "README.md", "environment.yml", "keys.py", "dist/",
])
def test_names_that_pass(path):
    assert rules.match(path) is None


def test_case_matters():
    assert rules.match(".ds_store") is None

