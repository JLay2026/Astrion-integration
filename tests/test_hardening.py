"""Regression tests for the three hardening patches (fork release 1.4.2-h1)."""
import json
import pathlib
import re

from homeassistant.setup import async_setup_component

from custom_components.astrion import config_flow

PKG = pathlib.Path(config_flow.__file__).parent

WS_COMMANDS = [
    ("astrion/submit_pair_data", {"code": "x", "data": {"serial_number": "SN1"}}),
    ("astrion/get_device_codes", {"entity_id": "remote.none"}),
    ("astrion/get_harmony_config", {}),
    ("astrion/get_broadlink_codes", {"entity_id": "remote.none"}),
]


# ---- patch 1: no vendor-cloud options flow ------------------------------

def test_no_options_flow():
    """The cloud IR-library options flow is gone."""
    assert not hasattr(config_flow, "MyIROptionsFlowHandler")
    assert "async_get_options_flow" not in config_flow.MyIRConfigFlow.__dict__


def test_no_outbound_http_anywhere():
    """No module imports an HTTP client or names the vendor API host."""
    pattern = re.compile(
        r"async_get_clientsession|aiohttp|lifex360|http\.client"
        r"|^\s*(import|from)\s+(requests|urllib|httpx)\b",
        re.MULTILINE,
    )
    for py in PKG.glob("*.py"):
        src = py.read_text(encoding="utf-8-sig")
        hit = pattern.search(src)
        assert hit is None, f"{hit.group(0)!r} found in {py.name}"


# ---- patch 2: websocket commands are admin-only -------------------------

async def _ws_results(hass, hass_ws_client, token):
    assert await async_setup_component(hass, "astrion", {})
    client = await hass_ws_client(hass, access_token=token)
    out = {}
    for i, (cmd, extra) in enumerate(WS_COMMANDS, start=1):
        await client.send_json({"id": i, "type": cmd, **extra})
        out[cmd] = await client.receive_json()
    return out


async def test_ws_rejects_non_admin(hass, hass_ws_client, hass_read_only_access_token):
    results = await _ws_results(hass, hass_ws_client, hass_read_only_access_token)
    for cmd, msg in results.items():
        assert msg["success"] is False, cmd
        assert msg["error"]["code"] == "unauthorized", (cmd, msg["error"])


async def test_ws_allows_admin(hass, hass_ws_client, hass_access_token):
    results = await _ws_results(hass, hass_ws_client, hass_access_token)
    for cmd, msg in results.items():
        # Admin reaches the handler: any answer except "unauthorized".
        if not msg["success"]:
            assert msg["error"]["code"] != "unauthorized", (cmd, msg["error"])
    assert results["astrion/submit_pair_data"]["success"] is True


# ---- patch 3: harmony reads run off the event loop and still work -------

async def test_harmony_config_reads_and_filters(hass, hass_ws_client, hass_access_token):
    cfg = pathlib.Path(hass.config.config_dir)
    (cfg / "harmony_hubA.conf").write_text(json.dumps({"activities": {"1": "TV"}}))
    (cfg / "harmony_hubB.conf").write_text(json.dumps({"activities": {}}))
    assert await async_setup_component(hass, "astrion", {})
    client = await hass_ws_client(hass, access_token=hass_access_token)

    await client.send_json({"id": 1, "type": "astrion/get_harmony_config"})
    msg = await client.receive_json()
    assert msg["success"], msg
    names = [h["hub_name"] for h in msg["result"]["hubs"]]
    assert names == ["hubA", "hubB"]
    assert msg["result"]["hubs"][0]["config"] == {"activities": {"1": "TV"}}


async def test_harmony_config_no_files(hass, hass_ws_client, hass_access_token):
    for leftover in pathlib.Path(hass.config.config_dir).glob("harmony_*.conf"):
        leftover.unlink()
    assert await async_setup_component(hass, "astrion", {})
    client = await hass_ws_client(hass, access_token=hass_access_token)
    await client.send_json({"id": 1, "type": "astrion/get_harmony_config"})
    msg = await client.receive_json()
    assert msg["success"] and msg["result"] == {"hubs": []}
