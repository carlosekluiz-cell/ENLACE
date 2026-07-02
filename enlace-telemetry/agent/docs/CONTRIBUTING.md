# Contributing to Pulso Agent

Thank you for your interest in contributing! The Pulso Agent is the open-source data collection layer for the Pulso Network ISP intelligence platform.

## How to Contribute

### Adding Support for a New OLT Vendor

This is the most impactful contribution. Here's how:

1. **Create a YAML device profile** in `profiles/`
   - Map the vendor's SNMP OIDs for ONT status, optical power, distance
   - Document CLI commands for data not available via SNMP
   - Include sysObjectID prefix for auto-detection

2. **Create a Rust collector** in `src/vendors/`
   - Implement the `OltCollector` trait
   - Use SNMP as primary data source, CLI as fallback
   - Follow the Huawei collector as a reference implementation

3. **Add test data** in `tests/simulator/`
   - Provide an snmpwalk recording from the real device (sanitize sensitive data)
   - This allows CI testing without physical hardware

4. **Submit a Pull Request** with:
   - The YAML profile
   - The Rust collector module
   - Test data
   - Brief description of the OLT models supported

### Getting SNMP Walk Data

Ask any ISP with the target OLT to run:
```bash
snmpwalk -v2c -c public -ObentU <OLT_IP> 1.3.6 > vendor_model.snmpwalk
```
This takes 2 minutes and produces a text file with all SNMP data.
Please sanitize customer MAC addresses and sensitive data before submitting.

## Code of Conduct

Be respectful. We're building tools for ISPs worldwide, many in developing countries. Every contribution helps connect communities.

## License

By contributing, you agree that your contributions will be licensed under Apache 2.0.
