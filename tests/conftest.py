"""Test setup for the hardened Astrion Home fork.

Upstream ships the integration in custom_components/my_ir while its manifest
domain is "astrion". HACS installs it under custom_components/astrion (named
after the domain), and HA's loader requires folder == domain, so the tests
(and CI) expose it under that name via a symlink created at session start.
"""
import os
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
LINK = ROOT / "custom_components" / "astrion"
if not LINK.exists():
    os.symlink("my_ir", LINK)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield
