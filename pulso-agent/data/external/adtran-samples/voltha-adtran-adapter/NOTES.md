# NOTES — VOLTHA Adtran OLT adapter (Adtran-authored NETCONF code)

- Source repo: https://github.com/opencord/voltha-adtran-adapter (branch master)
- License: Apache-2.0 (per-file headers: "Copyright 2017-present Adtran, Inc.")
- Download date: 2026-07-02
- What: the ONF VOLTHA/SEBA adapter for Adtran PON OLTs, written by Adtran. Not raw
  device output, but the code encodes the exact NETCONF request payloads and expected
  reply structures of real Adtran OLTs:
  - `adtran_netconf.py` — ncclient wrapper; `ADTRAN_NS = 'http://www.adtran.com/ns/yang'`,
    ietf-interfaces get filter, capability access, edit-config handling.
  - `codec/ietf_interfaces.py` — parses `<interfaces-state>` replies (real element names).
  - `codec/olt_state.py` — parses Adtran `gpon-olt-hw` PON state replies (pon-id, ONU
    status, gem/alloc IDs, RX power fields).
  - `codec/olt_config.py` — Adtran `gpon-olt-hw` config document structure.
  - `codec/physical_entities_state.py` — Adtran `adtran-physical-entities` state
    (hardware/transceiver inventory).
  - `pon_port.py` — builds real edit-config XML for PON ports (enable, downstream FEC,
    ONU authentication) against the Adtran namespace.
  - `adtran_olt_handler.py` — overall device handler incl. capability checks.
  - `mock_netconf_client.py` — Adtran's own mock of their NETCONF server behavior.
  - `README.md` — adapter documentation.

Source URL pattern: https://raw.githubusercontent.com/opencord/voltha-adtran-adapter/master/adapters/...
(original paths: adapters/adtran_common/net/, adapters/adtran_olt/, adapters/adtran_olt/codec/)

Caveat: this targets the pre-SDX-branding Adtran OLT generation used in SEBA pods and
Adtran's proprietary `gpon-olt-hw` model, not the bbf-xpon standard model that the
SDX 6320/6330 also exposes. Use together with ../obbaa-examples for the standard model.
