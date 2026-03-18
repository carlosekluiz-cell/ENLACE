// SPDX-License-Identifier: Apache-2.0
// Adtran SDX 6320 OLT Collector (OpenOLT gRPC)

use async_trait::async_trait;
use crate::config::OltConfig;
use super::*;

pub struct AdtranCollector {
    olt_id: String,
    config: OltConfig,
}

impl AdtranCollector {
    pub fn new(config: &OltConfig) -> anyhow::Result<Self> {
        Ok(Self {
            olt_id: format!("adtran-{}", config.ip.replace('.', "-")),
            config: config.clone(),
        })
    }
}

#[async_trait]
impl OltCollector for AdtranCollector {
    fn olt_id(&self) -> &str { &self.olt_id }
    fn vendor_name(&self) -> &str { "adtran" }

    async fn collect(&self) -> anyhow::Result<OltData> {
        anyhow::bail!("Adtran gRPC collector not yet implemented")
    }

    async fn test_connection(&self) -> anyhow::Result<bool> {
        Ok(false)
    }
}
