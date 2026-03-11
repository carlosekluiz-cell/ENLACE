# Open-Source Telecom Tools Research

**Date:** 2026-03-11
**Purpose:** Evaluate open-source telecom, network planning, and ISP management tools for potential integration with or complement to the Enlace platform (Python/Rust/TypeScript, PostgreSQL+PostGIS).

---

## Table of Contents

1. [Network Planning & Design](#1-network-planning--design)
2. [Spectrum & RF Tools](#2-spectrum--rf-tools)
3. [Telecom Data & APIs](#3-telecom-data--apis)
4. [ISP Operations Tools](#4-isp-operations-tools)
5. [Integration Priority Matrix](#5-integration-priority-matrix)

---

## 1. Network Planning & Design

### 1.1 NetBox — Network Source of Truth

| Field | Value |
|-------|-------|
| **URL** | https://github.com/netbox-community/netbox |
| **Stars** | ~20,000 |
| **License** | Apache 2.0 |
| **Language** | Python (94.7%) |
| **Active?** | Yes — latest release v4.5.4 (2026-03-03), very active development |
| **What it does** | The premier open-source network source of truth (NSoT). Combines IPAM (IP Address Management) and DCIM (Data Center Infrastructure Management) with powerful REST/GraphQL APIs. Models devices, circuits, cables, racks, sites, and providers. Used by Charter Communications, major telcos (5,000+ devices). |
| **Integration with Enlace** | **HIGH PRIORITY.** NetBox can serve as the definitive inventory for ISP infrastructure — towers, fiber routes, OLTs, splitters, and subscriber CPE. Its REST API (Django REST Framework) integrates trivially with Enlace's Python backend. Could replace or supplement our `providers` and `base_stations` tables with a richer, standards-based data model. The plugin ecosystem allows custom models for Brazilian telecom specifics (Anatel license references, SNIS compliance data). |
| **Effort** | Medium (2-3 weeks). Deploy NetBox alongside Enlace, build sync jobs to keep PostGIS tables in sync. Write a NetBox plugin for Enlace-specific models if needed. |

---

### 1.2 GNPy — Optical Route Planning Library

| Field | Value |
|-------|-------|
| **URL** | https://github.com/Telecominfraproject/oopt-gnpy |
| **Stars** | 239 |
| **License** | BSD-3-Clause |
| **Language** | Python (100%) |
| **Active?** | Yes — maintained by Telecom Infra Project (TIP), 1,589 commits |
| **What it does** | Community-developed library for building route planning and optimization tools for real-world mesh optical (DWDM) networks. Uses Gaussian Noise Model for optical feasibility simulation. Can act as a Path Computation Engine (PCE), track bandwidth requests, and advise SDN controllers about optimal paths through large DWDM networks. Supports amplifier placement, OSNR calculations, and fiber span analysis. |
| **Integration with Enlace** | **MEDIUM-HIGH.** Directly relevant for fiber backbone planning in the Enlace platform. Could extend our fiber route planning (currently Dijkstra on road segments) with optical-layer feasibility analysis — ensuring planned fiber routes are physically viable (span lengths, amplifier spacing, signal quality). Pure Python, so integrates cleanly with our FastAPI backend. |
| **Effort** | Medium (2-4 weeks). Import as a Python library, feed it topology data from our road_segments/fiber_routes tables, and expose optical feasibility results through new API endpoints. |

---

### 1.3 Net2Plan — Network Planner

| Field | Value |
|-------|-------|
| **URL** | https://github.com/girtel/Net2Plan |
| **Stars** | 93 |
| **License** | BSD-2-Clause |
| **Language** | Java (99.4%) |
| **Active?** | Moderate — 2,117 commits, academic project from Universidad Politecnica de Cartagena |
| **What it does** | Free Java tool for planning, optimization, and evaluation of communication networks. Technology-agnostic network representation (nodes, links, demands, routes). Includes optimization algorithms for WDM, IP, and multi-layer networks. CLI and GUI interfaces. Large repository of built-in algorithms for traffic engineering, protection, and grooming. |
| **Integration with Enlace** | **LOW-MEDIUM.** Useful algorithms but Java-based, making direct integration harder. Could be used as a standalone planning tool or wrapped via subprocess/REST adapter. The optimization algorithms (e.g., ILP-based routing and spectrum assignment) could complement our simulated annealing tower optimizer. |
| **Effort** | High (4-6 weeks). Would need a Java wrapper service or port algorithms to Python/Rust. |

---

### 1.4 FiberQ — QGIS Plugin for FTTx Design

| Field | Value |
|-------|-------|
| **URL** | https://github.com/vukovicvl/fiberq |
| **Stars** | 13 |
| **License** | GPL-3.0 |
| **Language** | QML (60.3%), Python (39.7%) |
| **Active?** | New project (14 commits), early but active development |
| **What it does** | Open-source QGIS plugin for designing fiber optic networks (FTTH/GPON/FTTx). Supports digitizing routes on basemaps, placing poles/manholes/ducts/cabinets/closures, building cable runs with branching logic, and exporting to GeoPackage/KML. Works with PostGIS for team collaboration. |
| **Integration with Enlace** | **MEDIUM.** The PostGIS backend aligns perfectly with our stack. Could adopt their data model for fiber network elements. The QGIS dependency limits direct web integration, but we could extract the Python algorithms for splitter placement and cable routing into our backend, or use it as a companion desktop tool for field engineers. |
| **Effort** | Medium (2-3 weeks). Extract algorithms or use as complementary desktop tool. |

---

### 1.5 Geospatial Network Inventory (GNI FREE)

| Field | Value |
|-------|-------|
| **URL** | https://ksavinetworkinventory.com/ftth-design-software-free/ |
| **Stars** | N/A (QGIS-based, not a standalone GitHub repo) |
| **License** | Open source (QGIS-based) |
| **Language** | Python/QGIS |
| **Active?** | Yes — commercial product with free tier |
| **What it does** | FTTH network planning tool based on QGIS platform. Combines vector libraries with FTTH/GPON engineering rules to automate fiber optic network design. Guides users from demand analysis through OLT placement, splice closure placement, cable profile recommendations, and splitter ratio optimization. |
| **Integration with Enlace** | **LOW-MEDIUM.** Best used as a standalone desktop companion. Not easily embeddable in a web platform, but concepts and data models are transferable. |
| **Effort** | Low (reference/companion tool). |

---

### 1.6 FTTH Planner

| Field | Value |
|-------|-------|
| **URL** | https://github.com/ChrisMolanus/ftth_planner |
| **Stars** | 8 |
| **License** | Not specified |
| **Language** | Python (100%) |
| **Active?** | Low activity — 340 commits |
| **What it does** | Application capable of creating viable Fiber to the Home planning given a set of postcodes. Pure Python, algorithmic approach to FTTH network design. |
| **Integration with Enlace** | **LOW.** Small project, but the algorithms for postcode-based FTTH planning could be adapted for Brazilian municipality-level planning. |
| **Effort** | Low (1-2 days to evaluate algorithms). |

---

### 1.7 PONC — PON Layout Optimizer

| Field | Value |
|-------|-------|
| **URL** | https://github.com/qoala101/ponc |
| **Stars** | 53 |
| **License** | MIT |
| **Language** | C++ (98.4%) |
| **Active?** | Moderate — 490 commits |
| **What it does** | Graphical tool for designing, managing, and optimizing Passive Optical Network layouts. Performs complex splitter combination calculations. Engineers design or refine PON layouts to find cheapest splitter combinations with instant reaction to changes and automatic layout calculations. |
| **Integration with Enlace** | **MEDIUM.** The splitter optimization algorithm is directly relevant to GPON network design. C++ is compatible with our Rust binary via FFI or could be rewritten in Rust. The optimization logic (finding cheapest splitter combinations) would enhance our rural fiber design capabilities. |
| **Effort** | Medium (2-3 weeks to port core algorithm to Rust or wrap as service). |

---

### 1.8 pgRouting — PostGIS Routing Engine

| Field | Value |
|-------|-------|
| **URL** | https://github.com/pgRouting/pgrouting |
| **Stars** | ~1,400 |
| **License** | GPL-2.0+ |
| **Language** | C++ (58.3%), C (20.1%) |
| **Active?** | Yes — very active, long-running project |
| **What it does** | Extends PostGIS/PostgreSQL with geospatial routing functionality. Provides Dijkstra, A*, driving distance/isochrone, TSP, and many more routing algorithms directly in SQL. Real-time routing against dynamically changing costs. |
| **Integration with Enlace** | **HIGH PRIORITY.** We already use PostGIS and have 6.4M road segments. pgRouting would replace our custom Python Dijkstra with battle-tested, SQL-native routing that runs orders of magnitude faster. Directly supports our fiber route planning, last-mile optimization, and service area analysis (isochrones). Already in our technology stack (PostgreSQL). |
| **Effort** | Low (3-5 days). Install pgRouting extension, create topology from road_segments table, replace Python routing with SQL queries. |

---

## 2. Spectrum & RF Tools

### 2.1 SPLAT! — RF Propagation Analysis

| Field | Value |
|-------|-------|
| **URL** | https://github.com/jmcmellen/splat (original), https://github.com/hoche/splat (enhanced fork) |
| **Stars** | 99 (original) |
| **License** | GPL-2.0 |
| **Language** | C++ (78.4%), C (18.4%) |
| **Active?** | Original is archived; hoche/splat fork is actively maintained with multi-threading |
| **What it does** | RF Signal Propagation, Loss, And Terrain analysis tool for 20 MHz to 20 GHz. Uses Longley-Rice ITM and ITWOM v3.0 models. Generates coverage maps, path loss calculations, terrain profiles, and obstruction analysis using SRTM elevation data. Applications include site engineering, wireless network design, frequency coordination, and broadcasting. |
| **Integration with Enlace** | **LOW.** Enlace already has a more capable Rust RF engine (9,000 LOC) with FSPL, Hata, P.530, P.1812, ITM, TR38.901, P.676, P.838, diffraction, and vegetation models. SPLAT! uses similar ITM/ITWOM models but in C++. Could serve as a validation reference. |
| **Effort** | N/A — our Rust engine is more advanced. |

---

### 2.2 Signal-Server — Multi-threaded RF Coverage Calculator

| Field | Value |
|-------|-------|
| **URL** | https://github.com/Cloud-RF/Signal-Server (archived), https://github.com/W3AXL/Signal-Server (active fork) |
| **Stars** | 14 (W3AXL fork) |
| **License** | GPL-2.0 |
| **Language** | C++ |
| **Active?** | Main repo archived; W3AXL fork updated 2025 |
| **What it does** | Multi-threaded radio propagation simulator producing 2D profile plots or 360-degree polar coverage plots. Originally powered CloudRF. Supports ITM/ITWOM, Hata, COST231, and ECC33 models. Outputs WGS-84 PPM bitmaps. |
| **Integration with Enlace** | **LOW.** Same as SPLAT! — our Rust engine already implements these models with better performance and tighter integration. Signal-Server's output format (PPM bitmaps) is less useful than our grid-point approach. |
| **Effort** | N/A — our Rust engine is more advanced. |

---

### 2.3 rf-signals — Rust RF Planning for WISPs

| Field | Value |
|-------|-------|
| **URL** | https://github.com/thebracket/rf-signals |
| **Stars** | 29 |
| **License** | GPL-2.0 |
| **Language** | JavaScript (84.8% — web UI), Rust (core algorithms) |
| **Active?** | Moderate — 133 commits |
| **What it does** | RF planning system for WISPs (Wireless ISPs). Pure Rust implementations of ITM3/Longley-Rice, HATA/COST123, FSPL, and Fresnel calculations. Includes SRTM .hgt reader. Originally ported from Cloud_RF's Signal Server. Bracket-Heat is the web UI for planning WISP installations. |
| **Integration with Enlace** | **MEDIUM.** The Rust RF algorithms overlap significantly with our `enlace-propagation` crate, but the SRTM reader and WISP-specific planning workflow could provide useful reference code. The web-based planning UI (Bracket-Heat) demonstrates a pattern we could adopt. Since both projects use Rust+SRTM, code sharing or algorithm comparison would be straightforward. |
| **Effort** | Low (1 week). Review and selectively port any algorithms we are missing (e.g., Fresnel zone calculations). |

---

### 2.4 NEC2++ — Antenna Simulation Engine

| Field | Value |
|-------|-------|
| **URL** | https://github.com/tmolteno/necpp |
| **Stars** | 287 |
| **License** | GPL-2.0 |
| **Language** | C++ (60.8%) |
| **Active?** | Moderate — established codebase, Python bindings available |
| **What it does** | C++ rewrite of the Numerical Electromagnetics Code (NEC-2) for modeling antenna radiation patterns. Faster execution, automatic error detection. Compiled into a library for integration into antenna design systems. Python, Ruby, and C/C++ bindings included. Analyzes radiating and scattering properties of structures. |
| **Integration with Enlace** | **MEDIUM.** Could enhance our RF coverage calculations by incorporating realistic antenna radiation patterns instead of idealized omni/sector patterns. The Python bindings make it integratable with our backend. Would enable site-specific coverage predictions accounting for actual antenna characteristics (gain, beamwidth, tilt, sidelobes). |
| **Effort** | Medium (2-3 weeks). Install Python bindings, create antenna pattern library for common Brazilian ISP antennas, integrate patterns into RF coverage calculations. |

---

### 2.5 Xnec2c — Interactive Antenna Visualization

| Field | Value |
|-------|-------|
| **URL** | https://github.com/KJ7LNW/xnec2c |
| **Stars** | 121 |
| **License** | GPL-3.0 |
| **Language** | C (92.4%) |
| **Active?** | Yes — actively maintained |
| **What it does** | GTK3-based graphical NEC2 antenna simulator. Interactive visualization of radiation patterns, impedance plots, VSWR graphs, current distributions. Real-time parameter tuning with instant visual feedback. Multi-threaded computation. |
| **Integration with Enlace** | **LOW.** Desktop GUI tool, not web-integratable. Useful as a companion tool for antenna engineers designing custom antenna configurations, but not for platform integration. |
| **Effort** | N/A — desktop companion tool only. |

---

### 2.6 QSpectrumAnalyzer — SDR Spectrum Analysis

| Field | Value |
|-------|-------|
| **URL** | https://github.com/xmikos/qspectrumanalyzer |
| **Stars** | ~1,400 |
| **License** | GPL-3.0 |
| **Language** | Python (99.3%) |
| **Active?** | Stable — 109 commits, feature-complete |
| **What it does** | Universal spectrum analyzer supporting nearly all SDR platforms (RTL-SDR, HackRF, Airspy, SDRplay, LimeSDR, bladeRF, USRP). PyQtGraph-based GUI supporting multiple backends (soapy_power, hackrf_sweep, rtl_power). Frequency sweeps, waterfall displays, peak detection. |
| **Integration with Enlace** | **MEDIUM.** Could enable field spectrum measurements for interference analysis and spectrum occupancy surveys. ISPs deploying in new areas could use SDR hardware + QSpectrumAnalyzer to validate spectrum availability before tower deployment. Data could feed into our satellite/coverage analysis. |
| **Effort** | Low-Medium (1-2 weeks). Would require SDR hardware in the field. Integration is at the data level — import spectrum measurement results into Enlace for planning. |

---

## 3. Telecom Data & APIs

### 3.1 OpenCelliD — Cell Tower Database

| Field | Value |
|-------|-------|
| **URL** | https://opencellid.org/ |
| **Stars** | N/A (data project, not a GitHub repo) |
| **License** | CC BY-SA 4.0 |
| **Data Size** | 40M+ cell tower records globally |
| **Active?** | Yes — continuously updated by community |
| **What it does** | World's largest open database of cell tower locations with GPS coordinates. Covers GSM, LTE, UMTS, 5G NR towers globally. Community-contributed data similar to OpenStreetMap. API access and bulk downloads available. |
| **Integration with Enlace** | **HIGH PRIORITY.** Directly complements our 37,727 OSM-sourced base stations with cell-level data (not just physical towers but individual cells with frequencies, MCC/MNC codes). Could enrich our competitive intelligence — knowing exactly which frequencies competitors use in each municipality. Bulk download for Brazil, import into PostGIS, cross-reference with our Anatel provider data. |
| **Effort** | Low (3-5 days). Download Brazil CSV, parse, import into PostGIS with cell_towers table, build JOIN queries against existing provider/municipality data. |

---

### 3.2 Ookla Open Data — Speedtest Performance

| Field | Value |
|-------|-------|
| **URL** | https://github.com/teamookla/ookla-open-data |
| **Stars** | 290 |
| **License** | CC BY-NC-SA 4.0 |
| **Language** | Jupyter Notebook (99.9%) |
| **Active?** | Yes — quarterly updates through Q4 2025 |
| **What it does** | Global fixed broadband and mobile network performance metrics in zoom-level-16 web Mercator tiles (~611m x 611m). Download speed, upload speed, and latency averaged per tile. Data from Q1 2019 through Q4 2025. Available as Shapefiles and Apache Parquet with WKT geometries (EPSG:4326). Hosted on AWS S3. |
| **Integration with Enlace** | **HIGH PRIORITY.** Extremely valuable for competitive intelligence. Overlaying Ookla speed data on our municipality map would show actual broadband performance by area — revealing underserved zones where ISPs could expand. Parquet format with WKT geometries integrates directly with our PostGIS pipeline. Could populate a `speed_measurements` table and join against municipalities for gap analysis. |
| **Effort** | Low (3-5 days). Download Brazil Parquet tiles from S3, import into PostGIS, create spatial joins with admin_level_2 geometries. Build API endpoint and frontend visualization. |

---

### 3.3 M-Lab (Measurement Lab) — NDT Speed Test Data

| Field | Value |
|-------|-------|
| **URL** | https://github.com/m-lab/ndt-server |
| **Stars** | 125 |
| **License** | Apache 2.0 |
| **Language** | Go (67.4%) |
| **Active?** | Yes — v0.25.0 released January 2026 |
| **What it does** | World's largest open internet measurement platform. NDT (Network Diagnostic Tool) measures connection capacity — upload/download speeds and latency. Over 1 million tests/day. All data publicly available on Google BigQuery and Google Cloud Storage. Raw measurement data including TCP diagnostics, traceroutes, and server-side metrics. |
| **Integration with Enlace** | **MEDIUM-HIGH.** More granular than Ookla (individual test results vs. aggregated tiles) but requires BigQuery access. Could query M-Lab BigQuery for Brazil-specific measurements and import into our database. Provides ISP-level performance data (AS numbers), enabling ISP-vs-ISP quality comparisons at the municipality level. |
| **Effort** | Medium (1-2 weeks). Set up BigQuery access, write ETL for Brazil data, import into PostGIS with ISP/AS attribution. |

---

### 3.4 RIPE Atlas — Internet Measurement Network

| Field | Value |
|-------|-------|
| **URL** | https://github.com/RIPE-NCC/ripe-atlas-tools |
| **Stars** | 201 |
| **License** | GPL-3.0 |
| **Language** | Python (99.9%) |
| **Active?** | Yes — maintained by RIPE NCC |
| **What it does** | Global network of hardware probes and anchors actively measuring Internet connectivity. Provides ping, traceroute, DNS, SSL/TLS, NTP, and HTTP measurements. All data is open and available via API. Python tools for scheduling measurements and analyzing results. Cousteau (Python API client) and Sagan (result parser) libraries. |
| **Integration with Enlace** | **MEDIUM.** Useful for ISP quality monitoring — deploy RIPE Atlas probes at ISP POPs to continuously monitor latency, packet loss, and routing to major content providers. Python libraries integrate easily with our backend. Could feed a real-time "network health" dashboard per ISP/region. |
| **Effort** | Medium (2-3 weeks). Requires deploying physical probes. API integration is straightforward with Cousteau library. |

---

### 3.5 awesome-telco — Curated Resource List

| Field | Value |
|-------|-------|
| **URL** | https://github.com/ravens/awesome-telco |
| **Stars** | N/A (curated list) |
| **License** | N/A |
| **Active?** | Yes — community maintained |
| **What it does** | Curated list of telecom resources and projects. Covers 5G core (Open5GS, Free5GC, OAI), RAN simulators (UERANSIM, srsRAN), SDR tools (gr-gsm, QCSuper), protocol libraries (pycrate), and more. Excellent reference for discovering niche telecom tools. |
| **Integration with Enlace** | Reference resource — not directly integratable but invaluable for ongoing discovery. |
| **Effort** | N/A — reference only. |

---

## 4. ISP Operations Tools

### 4.1 LibreNMS — Network Monitoring

| Field | Value |
|-------|-------|
| **URL** | https://github.com/librenms/librenms |
| **Stars** | ~4,600 |
| **License** | GPL-3.0 |
| **Language** | PHP (90.7%) |
| **Active?** | Yes — very active, continuous releases |
| **What it does** | Auto-discovering network monitoring system supporting SNMP v1/2c/3, CDP/LLDP/FDP discovery, and ARP table scanning. Supports 100+ vendors. Features include bandwidth billing, alerting, distributed polling, API, and multi-tenant capabilities. Docker and OVA deployment options. Specifically used by ISPs — Wavedirect Telecommunications contributed wireless device support. |
| **Integration with Enlace** | **HIGH PRIORITY.** The ideal complement for ISP operations monitoring. While Enlace focuses on planning and intelligence, LibreNMS handles real-time network health. Integration via LibreNMS API — pull device status, bandwidth utilization, and alert data into Enlace dashboards. Combined view: Enlace shows market opportunity + LibreNMS shows current network performance. |
| **Effort** | Medium (2-3 weeks). Deploy LibreNMS, configure SNMP polling for ISP equipment, build API bridge to pull key metrics into Enlace dashboards. |

---

### 4.2 OpenWISP — WiFi/Network Controller

| Field | Value |
|-------|-------|
| **URL** | https://github.com/openwisp/openwisp-controller (701 stars), https://github.com/openwisp/openwisp-monitoring (215 stars) |
| **Stars** | 701 (controller), 215 (monitoring) |
| **License** | BSD-3-Clause |
| **Language** | Python (87.3%) |
| **Active?** | Yes — Google Summer of Code 2025, active roadmap to 2030 |
| **What it does** | Open-source network management system for OpenWrt-based networks. Controller handles provisioning, configuration management, firmware upgrades, VPN configuration, and x509 PKI management. Monitoring module provides automated metric collection, alerting, and health checks. Designed for ISPs managing fleets of CPE devices (routers, access points). |
| **Integration with Enlace** | **MEDIUM-HIGH.** Highly relevant for ISPs using OpenWrt CPE. Python/Django stack aligns with our backend. OpenWISP monitoring data (per-device metrics, network topology) could feed Enlace's network health indicators. The provisioning system could complement our design tool — once Enlace designs a network, OpenWISP deploys and manages it. |
| **Effort** | Medium (2-4 weeks). Deploy OpenWISP, integrate via Django REST API, pull monitoring metrics into Enlace. |

---

### 4.3 Zabbix — Enterprise Monitoring

| Field | Value |
|-------|-------|
| **URL** | https://github.com/zabbix/zabbix |
| **Stars** | ~5,700 |
| **License** | AGPL-3.0 |
| **Language** | C, PHP, Go |
| **Active?** | Yes — v7.0 LTS released 2025, very active |
| **What it does** | Enterprise-class open-source monitoring for networks, servers, VMs, applications, and cloud. Built-in auto-discovery, alerting, visualization, SLA reporting, and API. Template-based monitoring for 100+ device types. Proxy high-availability, synthetic web monitoring. Scales to monitoring 100,000+ devices. |
| **Integration with Enlace** | **MEDIUM.** More general-purpose than LibreNMS (not ISP-specific). Best for organizations that need unified monitoring across infrastructure (not just network). SLA reporting feature is valuable for ISP compliance tracking. REST API enables integration with Enlace dashboards. |
| **Effort** | Medium (2-3 weeks). Deploy Zabbix, configure templates for telecom equipment, build API bridge. |

---

### 4.4 FreeRADIUS — AAA Server

| Field | Value |
|-------|-------|
| **URL** | https://github.com/FreeRADIUS/freeradius-server |
| **Stars** | ~2,500 |
| **License** | GPL-2.0 |
| **Language** | C (92.9%) |
| **Active?** | Yes — 51,795 commits, v4 in development |
| **What it does** | World's most widely deployed RADIUS server. Provides Authentication, Authorization, and Accounting (AAA) for ISPs, telcos, Fortune-500 companies, and Tier 1 ISPs. Supports all common protocols (PAP, CHAP, MS-CHAP, EAP, PEAP). Handles millions of subscriber sessions. SQL, LDAP, and REST backends. |
| **Integration with Enlace** | **MEDIUM.** Not directly an intelligence tool, but subscriber authentication data from FreeRADIUS contains valuable operational metrics — active subscribers per PoP, session durations, bandwidth consumption. This data could feed Enlace's subscriber analytics. Many Brazilian ISPs already use FreeRADIUS; integration means tapping existing data. |
| **Effort** | Low (1 week). Read FreeRADIUS accounting records from SQL backend, build ETL into Enlace analytics. |

---

### 4.5 daloRADIUS — RADIUS Web Management

| Field | Value |
|-------|-------|
| **URL** | https://github.com/lirantal/daloradius |
| **Stars** | 855 |
| **License** | GPL-2.0 |
| **Language** | PHP (87.9%) |
| **Active?** | Yes — 2,450 commits, v1.3 released |
| **What it does** | Advanced RADIUS web management application for ISP deployments. User management, graphical reporting, accounting, billing engine, and OpenStreetMap geolocation integration. Works on top of FreeRADIUS, sharing the same backend database. Manages hotspots and general ISP subscriber bases. |
| **Integration with Enlace** | **LOW-MEDIUM.** PHP-based, so not directly embeddable. But its data model for subscriber management and billing could inform Enlace's subscriber analytics features. If an ISP uses daloRADIUS, we can read their database to populate our subscriber metrics. |
| **Effort** | Low (3-5 days). Read-only database integration to pull subscriber counts and usage patterns. |

---

### 4.6 Ubilling — ISP Billing System

| Field | Value |
|-------|-------|
| **URL** | https://github.com/nightflyza/Ubilling |
| **Stars** | 171 |
| **License** | GPL-2.0 |
| **Language** | PHP (83.3%) |
| **Active?** | Yes — 7,517 commits, mature codebase |
| **What it does** | Open-source billing system for ISPs. Subscriber management, payment handling, detailed reporting. Controls and monitors network equipment (switches, OLTs, ONU). Extensible with custom modules. Based on Stargazer kernel. Supports IPoE, PPPoE, PPTP, L2TP, and PON technologies. |
| **Integration with Enlace** | **LOW-MEDIUM.** PHP-based, similar limitations as daloRADIUS. Subscriber and billing data would be valuable for Enlace's market intelligence — understanding ISP subscriber churn, ARPU, and service distribution. Read-only database integration. |
| **Effort** | Low (3-5 days). Database read integration for subscriber analytics. |

---

### 4.7 NOC Project — Telecom OSS

| Field | Value |
|-------|-------|
| **URL** | https://github.com/nocproject/noc |
| **Stars** | 135 |
| **License** | BSD-3-Clause |
| **Language** | Python (79.4%) |
| **Active?** | Yes — 41,125 commits, massive codebase (est. 132 person-years) |
| **What it does** | Scalable, high-performance OSS for telecom companies, service providers, and enterprise NOCs. Supports 100+ vendors. Network discovery, fault management, performance management, inventory, service activation. Scales from single-node to clusters managing millions of objects. Grafana integration for dashboards. |
| **Integration with Enlace** | **MEDIUM.** Python-based and BSD-licensed — the most compatible NOC solution. Its fault/performance management data would complement Enlace's planning intelligence. Could serve as the operational backend while Enlace handles strategic planning. API-based integration with our FastAPI backend. |
| **Effort** | High (4-6 weeks). NOC is a large, complex system. Full deployment is a project in itself. API integration is simpler. |

---

### 4.8 Grafana + NOC Dashboards

| Field | Value |
|-------|-------|
| **URL** | https://github.com/onfsdn/noc (Grafana-based NOC dashboard) |
| **Stars** | Varies by project |
| **License** | Apache 2.0 (Grafana) |
| **Language** | JSON (dashboards), Go (Grafana) |
| **Active?** | Yes — Grafana is one of the most active open-source projects |
| **What it does** | NOC dashboards built on Grafana for real-time network operations monitoring. Typically uses TIG stack (Telegraf + InfluxDB + Grafana) for data collection, storage, and visualization. Pre-built dashboards for network availability, bandwidth utilization, SLA tracking. |
| **Integration with Enlace** | **MEDIUM.** Grafana could serve as an alternative dashboard layer for operational metrics, while Enlace's Next.js frontend handles strategic/planning views. Grafana's data source plugin architecture means it could query Enlace's PostgreSQL directly. |
| **Effort** | Low (1 week). Deploy Grafana, configure PostgreSQL data source pointing to Enlace database, build NOC-focused dashboards. |

---

## 5. Integration Priority Matrix

### Tier 1 — High Priority, Low-Medium Effort (Implement within 1-2 sprints)

| Tool | Why | Effort |
|------|-----|--------|
| **pgRouting** | Already using PostGIS + 6.4M road segments. Drop-in upgrade to SQL-native routing. Replaces custom Python Dijkstra. | 3-5 days |
| **Ookla Open Data** | Parquet + WKT geometry directly into PostGIS. Immediate competitive intelligence value. | 3-5 days |
| **OpenCelliD** | CSV import into PostGIS. Enriches our 37K base stations with cell-level data (frequencies, operators). | 3-5 days |

### Tier 2 — High Priority, Medium Effort (Implement within 1-2 months)

| Tool | Why | Effort |
|------|-----|--------|
| **NetBox** | Standards-based network inventory. Apache 2.0. Python/Django. REST API aligns with our stack. | 2-3 weeks |
| **LibreNMS** | Real-time network monitoring complement. ISP-specific features (bandwidth billing, multi-tenant). | 2-3 weeks |
| **GNPy** | Pure Python optical planning library. Extends our fiber route planning with optical feasibility. | 2-4 weeks |
| **M-Lab BigQuery** | Granular speed test data with ISP attribution. Enables ISP quality benchmarking. | 1-2 weeks |

### Tier 3 — Medium Priority, Selective Integration

| Tool | Why | Effort |
|------|-----|--------|
| **OpenWISP** | Relevant for ISPs using OpenWrt CPE. Python/Django alignment. | 2-4 weeks |
| **NEC2++** | Realistic antenna patterns for RF coverage. Python bindings available. | 2-3 weeks |
| **rf-signals** | Rust RF reference code. Selective algorithm porting. | 1 week |
| **PONC** | PON splitter optimization algorithm for GPON design. | 2-3 weeks |
| **FiberQ** | QGIS fiber design algorithms extractable for backend use. | 2-3 weeks |
| **QSpectrumAnalyzer** | Field spectrum measurement data import. Requires SDR hardware. | 1-2 weeks |
| **FreeRADIUS data** | Tap existing ISP subscriber/accounting data. | 1 week |
| **RIPE Atlas** | Internet quality monitoring with physical probes. | 2-3 weeks |

### Tier 4 — Reference / Companion Tools

| Tool | Why | Notes |
|------|-----|-------|
| **Zabbix** | General-purpose monitoring, less ISP-specific than LibreNMS | Alternative to LibreNMS |
| **NOC Project** | Full OSS platform, very large deployment | Too complex for quick integration |
| **Net2Plan** | Java-based, optimization algorithms could be ported | Academic reference |
| **SPLAT! / Signal-Server** | Our Rust RF engine is already more capable | Validation reference only |
| **daloRADIUS / Ubilling** | PHP-based billing/subscriber management | Read-only data extraction |
| **Xnec2c** | Desktop antenna visualization | Field engineer companion |
| **awesome-telco** | Curated list for ongoing tool discovery | Bookmark and revisit |

---

## Key Recommendations

1. **Immediate wins (this week):** Install pgRouting, import Ookla and OpenCelliD data. These three actions require minimal effort and deliver immediate analytical value.

2. **Next month:** Deploy NetBox as the network inventory backbone and LibreNMS for operational monitoring. These establish the operational data layer that Enlace's intelligence layer feeds from.

3. **Ongoing:** Build data pipelines to ingest M-Lab speed test data (via BigQuery) and RIPE Atlas measurements for continuous quality benchmarking.

4. **Architecture principle:** Enlace should position itself as the **intelligence and planning layer** that sits on top of operational tools (NetBox for inventory, LibreNMS/Zabbix for monitoring, FreeRADIUS for AAA). Enlace's unique value is the combination of market intelligence, RF engineering, and geospatial analysis — not operational network management.

5. **License considerations:** Prefer Apache 2.0 and BSD-licensed tools (NetBox, GNPy, pgRouting, NOC) over GPL tools for tighter integration. GPL tools (LibreNMS, FreeRADIUS, SPLAT!) are fine as standalone complements accessed via API.

---

## Sources

- [NetBox - GitHub](https://github.com/netbox-community/netbox)
- [GNPy - Telecom Infra Project](https://github.com/Telecominfraproject/oopt-gnpy)
- [Net2Plan - GitHub](https://github.com/girtel/Net2Plan)
- [FiberQ - GitHub](https://github.com/vukovicvl/fiberq)
- [GNI FREE - KSavi](https://ksavinetworkinventory.com/ftth-design-software-free/)
- [FTTH Planner - GitHub](https://github.com/ChrisMolanus/ftth_planner)
- [PONC - GitHub](https://github.com/qoala101/ponc)
- [pgRouting - GitHub](https://github.com/pgRouting/pgrouting)
- [SPLAT! - GitHub](https://github.com/jmcmellen/splat)
- [Signal-Server - GitHub (W3AXL fork)](https://github.com/W3AXL/Signal-Server)
- [rf-signals - GitHub](https://github.com/thebracket/rf-signals)
- [NEC2++ - GitHub](https://github.com/tmolteno/necpp)
- [Xnec2c - GitHub](https://github.com/KJ7LNW/xnec2c)
- [QSpectrumAnalyzer - GitHub](https://github.com/xmikos/qspectrumanalyzer)
- [OpenCelliD](https://opencellid.org/)
- [Ookla Open Data - GitHub](https://github.com/teamookla/ookla-open-data)
- [M-Lab NDT Server - GitHub](https://github.com/m-lab/ndt-server)
- [RIPE Atlas Tools - GitHub](https://github.com/RIPE-NCC/ripe-atlas-tools)
- [awesome-telco - GitHub](https://github.com/ravens/awesome-telco)
- [LibreNMS - GitHub](https://github.com/librenms/librenms)
- [OpenWISP Controller - GitHub](https://github.com/openwisp/openwisp-controller)
- [OpenWISP Monitoring - GitHub](https://github.com/openwisp/openwisp-monitoring)
- [Zabbix - GitHub](https://github.com/zabbix/zabbix)
- [FreeRADIUS - GitHub](https://github.com/FreeRADIUS/freeradius-server)
- [daloRADIUS - GitHub](https://github.com/lirantal/daloradius)
- [Ubilling - GitHub](https://github.com/nightflyza/Ubilling)
- [NOC Project - GitHub](https://github.com/nocproject/noc)
- [UERANSIM - GitHub](https://github.com/aligungr/UERANSIM)
- [Ookla Speedtest on AWS](https://registry.opendata.aws/speedtest-global-performance/)
- [M-Lab Measurement Lab](https://www.measurementlab.net/)
- [RIPE Atlas](https://atlas.ripe.net/)
- [OpenWISP](https://openwisp.org/)
- [FreeRADIUS](https://www.freeradius.org/)
- [Zabbix](https://www.zabbix.com/)
- [pgRouting](http://pgrouting.org/)
