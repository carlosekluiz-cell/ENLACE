# NOTES — Broadband Forum YANG modules (bbf-xpon family)

Source repo: https://github.com/BroadbandForum/yang (branch: master)
License: BSD-3-Clause (see LICENSE in this directory; each module also carries the BBF license header)
Download date: 2026-07-02
Purpose: reference schemas for validating the Adtran SDX (XGS-PON OLT) NETCONF/YANG parser in pulso-agent.
Selection: all bbf-xpon*, bbf-xponani*, bbf-xponvani*, bbf-xpongemtcont* modules from standard/interface/,
plus bbf-hardware-transceivers*, bbf-hardware-types*, bbf-hardware.yang from standard/equipment/ and standard/interface/.

| File | Original repo path | Source URL |
|---|---|---|
| LICENSE | LICENSE | https://raw.githubusercontent.com/BroadbandForum/yang/master/LICENSE |
| bbf-hardware-transceiver-alarm-types.yang | standard/equipment/bbf-hardware-transceiver-alarm-types.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/equipment/bbf-hardware-transceiver-alarm-types.yang |
| bbf-hardware-transceivers-xpon.yang | standard/interface/bbf-hardware-transceivers-xpon.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-hardware-transceivers-xpon.yang |
| bbf-hardware-transceivers.yang | standard/equipment/bbf-hardware-transceivers.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/equipment/bbf-hardware-transceivers.yang |
| bbf-hardware-types-xpon.yang | standard/interface/bbf-hardware-types-xpon.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-hardware-types-xpon.yang |
| bbf-hardware-types.yang | standard/equipment/bbf-hardware-types.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/equipment/bbf-hardware-types.yang |
| bbf-hardware.yang | standard/equipment/bbf-hardware.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/equipment/bbf-hardware.yang |
| bbf-xpon-base.yang | standard/interface/bbf-xpon-base.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xpon-base.yang |
| bbf-xpon-burst-profiles.yang | standard/interface/bbf-xpon-burst-profiles.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xpon-burst-profiles.yang |
| bbf-xpon-channel-group-body.yang | standard/interface/bbf-xpon-channel-group-body.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xpon-channel-group-body.yang |
| bbf-xpon-channel-pair-body.yang | standard/interface/bbf-xpon-channel-pair-body.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xpon-channel-pair-body.yang |
| bbf-xpon-channel-partition-body.yang | standard/interface/bbf-xpon-channel-partition-body.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xpon-channel-partition-body.yang |
| bbf-xpon-channel-termination-body.yang | standard/interface/bbf-xpon-channel-termination-body.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xpon-channel-termination-body.yang |
| bbf-xpon-defects.yang | standard/interface/bbf-xpon-defects.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xpon-defects.yang |
| bbf-xpon-if-type.yang | standard/interface/bbf-xpon-if-type.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xpon-if-type.yang |
| bbf-xpon-multicast-distribution-set-body.yang | standard/interface/bbf-xpon-multicast-distribution-set-body.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xpon-multicast-distribution-set-body.yang |
| bbf-xpon-multicast-gemport-body.yang | standard/interface/bbf-xpon-multicast-gemport-body.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xpon-multicast-gemport-body.yang |
| bbf-xpon-onu-authentication-features.yang | standard/interface/bbf-xpon-onu-authentication-features.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xpon-onu-authentication-features.yang |
| bbf-xpon-onu-authentication-types.yang | standard/interface/bbf-xpon-onu-authentication-types.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xpon-onu-authentication-types.yang |
| bbf-xpon-onu-authentication.yang | standard/interface/bbf-xpon-onu-authentication.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xpon-onu-authentication.yang |
| bbf-xpon-onu-state.yang | standard/interface/bbf-xpon-onu-state.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xpon-onu-state.yang |
| bbf-xpon-onu-types.yang | standard/interface/bbf-xpon-onu-types.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xpon-onu-types.yang |
| bbf-xpon-performance-management.yang | standard/interface/bbf-xpon-performance-management.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xpon-performance-management.yang |
| bbf-xpon-power-management.yang | standard/interface/bbf-xpon-power-management.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xpon-power-management.yang |
| bbf-xpon-types.yang | standard/interface/bbf-xpon-types.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xpon-types.yang |
| bbf-xpon-wavelength-profile-body.yang | standard/interface/bbf-xpon-wavelength-profile-body.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xpon-wavelength-profile-body.yang |
| bbf-xpon.yang | standard/interface/bbf-xpon.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xpon.yang |
| bbf-xponani-ani-body.yang | standard/interface/bbf-xponani-ani-body.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xponani-ani-body.yang |
| bbf-xponani-base.yang | standard/interface/bbf-xponani-base.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xponani-base.yang |
| bbf-xponani-power-management.yang | standard/interface/bbf-xponani-power-management.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xponani-power-management.yang |
| bbf-xponani-v-enet-body.yang | standard/interface/bbf-xponani-v-enet-body.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xponani-v-enet-body.yang |
| bbf-xponani.yang | standard/interface/bbf-xponani.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xponani.yang |
| bbf-xpongemtcont-base.yang | standard/interface/bbf-xpongemtcont-base.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xpongemtcont-base.yang |
| bbf-xpongemtcont-gemport-body.yang | standard/interface/bbf-xpongemtcont-gemport-body.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xpongemtcont-gemport-body.yang |
| bbf-xpongemtcont-gemport-performance-management.yang | standard/interface/bbf-xpongemtcont-gemport-performance-management.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xpongemtcont-gemport-performance-management.yang |
| bbf-xpongemtcont-qos.yang | standard/interface/bbf-xpongemtcont-qos.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xpongemtcont-qos.yang |
| bbf-xpongemtcont-tcont-body.yang | standard/interface/bbf-xpongemtcont-tcont-body.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xpongemtcont-tcont-body.yang |
| bbf-xpongemtcont-traffic-descriptor-profile-body.yang | standard/interface/bbf-xpongemtcont-traffic-descriptor-profile-body.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xpongemtcont-traffic-descriptor-profile-body.yang |
| bbf-xpongemtcont.yang | standard/interface/bbf-xpongemtcont.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xpongemtcont.yang |
| bbf-xponvani-base.yang | standard/interface/bbf-xponvani-base.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xponvani-base.yang |
| bbf-xponvani-onu-authentication-groupings.yang | standard/interface/bbf-xponvani-onu-authentication-groupings.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xponvani-onu-authentication-groupings.yang |
| bbf-xponvani-onu-authentication.yang | standard/interface/bbf-xponvani-onu-authentication.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xponvani-onu-authentication.yang |
| bbf-xponvani-power-management.yang | standard/interface/bbf-xponvani-power-management.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xponvani-power-management.yang |
| bbf-xponvani-v-ani-body.yang | standard/interface/bbf-xponvani-v-ani-body.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xponvani-v-ani-body.yang |
| bbf-xponvani-v-enet-body.yang | standard/interface/bbf-xponvani-v-enet-body.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xponvani-v-enet-body.yang |
| bbf-xponvani.yang | standard/interface/bbf-xponvani.yang | https://raw.githubusercontent.com/BroadbandForum/yang/master/standard/interface/bbf-xponvani.yang |
