# Hardened fork of Astrion Home

This is a security-hardened fork of [yyqclhy/Astrion-integration](https://github.com/yyqclhy/Astrion-integration) ("Astrion Home", HA domain `astrion`), the Home Assistant companion integration for the Sanytron Astrion remote. It is maintained for one household and is not a general distribution.

## Policy

- **Patches are security and correctness only.** No features. The fork tracks upstream and stays as close to it as possible, so each vendor release rebases mechanically.
- **Version-matched to the vendor.** Sanytron requires firmware, RosCard and Astrion Home to be on the same version. Fork releases carry the upstream version plus a hardening suffix: `1.4.2-h1` is upstream 1.4.2 plus hardening revision 1.
- **Pinned install.** Install from a tagged release of this fork through HACS, with auto-update off. Read every upstream release's diff before rebasing.

## Provenance

| | |
|---|---|
| Upstream release | `v1.4.2`, commit `66bf40fc4b5e886fae783ff238d705d2e257ea4d` (2026-08-06) |
| Fork base | `0c325d60f18d69534611bba2a1fa9a662a9befef` (upstream README edits only after v1.4.2) |
| Source review | All files read 2026-10-24: `__init__.py`, `config_flow.py`, `remote.py`, `select.py`, `button.py`, `services.yaml`, `const.py`, `manifest.json` |

## Patches (1.4.2-h1)

1. **No vendor-cloud requests.** Upstream's options flow (the integration's "Configure" button) downloaded IR code libraries from the vendor's cloud API, with unauthenticated GETs from the HA host. That flow is removed. The integration now makes no outbound internet requests. Pairing, the page selects, the refresh button, and the Harmony and Broadlink pass-through are unaffected. The only loss is the cloud IR code library for the remote's built-in IR blaster.
2. **WebSocket commands are admin-only.** `astrion/submit_pair_data`, `get_device_codes`, `get_harmony_config` and `get_broadlink_codes` were callable by any authenticated user. They now require an admin. The remote already authenticates with an admin token, since the vendor requires one, so it is unaffected.
3. **Harmony config reads run off the event loop.** The `get_harmony_config` WebSocket handler globbed and read files synchronously on HA's event loop. Those reads now run in the executor. Output is unchanged.

The manifest's `documentation` and `issue_tracker` now point at this fork.

## Reviewed and left alone (upstream behaviour, low risk)

- `select.py`: the "Navigate Action" select listens to every `state_changed` event and filters by its own entity. That's inefficient but harmless.
- `remote.py`: sets `entity_id` directly. It only applies to IR devices created by the removed cloud flow.
- `services.yaml` documents `initiate_pairing` and `remove_device`, which are never registered.
- Four cosmetic lint findings (unused imports and variables), identical to upstream.
- Events fired to the remote (`astrion/pair_request`, `control_command`, `navigate_to`, `refresh_request`) carry only serials, page names and button codes.

## Gates (`.github/workflows/ci.yml`)

| Job | Required | What it proves |
|---|---|---|
| tests | yes | `tests/test_hardening.py`: each patch holds, and Harmony output is unchanged |
| negative-control | yes | the same security tests **fail** on unmodified upstream v1.4.2, so the suite can detect a missing patch |
| static | yes | ruff (syntax and undefined names), bandit (medium and above), no outbound HTTP clients |
| actionlint | yes | workflow syntax |
| hassfest | advisory | HA manifest and translations validation, with the folder presented under its domain name |
| hacs | advisory | HACS repository validation |

Upstream ships the code in `custom_components/my_ir` while the domain is `astrion`. HACS installs it as `custom_components/astrion`. The tests and the hassfest job present it under that name. The folder is not renamed, to keep rebases clean.

## Rebasing onto a new upstream release

1. Read the upstream release diff in full.
2. Rebase this fork's patch commits onto the new tag. Update `UPSTREAM_TAG`/`UPSTREAM_SHA` in the negative-control job and the provenance table above.
3. All required gates green. Bump the manifest to `<upstream>-h1`.
4. Tag the release and update through HACS, coordinated with the firmware and RosCard versions.
