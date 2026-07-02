// SPDX-License-Identifier: Apache-2.0
// Intelbras OLT Collector (G08, G16 — native firmware)
// Note: Intelbras-branded FiberHome AN5516/AN6001 use FiberhomeCollector instead.
// Native Intelbras G-series uses FiberHome OIDs with same enterprise prefix.

use async_trait::async_trait;
use crate::config::OltConfig;
use super::*;

pub struct IntelbrasCollector {
    inner: super::fiberhome::FiberhomeCollector,
    olt_id: String,
}

impl IntelbrasCollector {
    pub fn new(config: &OltConfig) -> anyhow::Result<Self> {
        let inner = super::fiberhome::FiberhomeCollector::new(config)?;
        Ok(Self {
            olt_id: format!("intelbras-{}", config.ip.replace('.', "-")),
            inner,
        })
    }
}

#[async_trait]
impl OltCollector for IntelbrasCollector {
    fn olt_id(&self) -> &str { &self.olt_id }
    fn vendor_name(&self) -> &str { "intelbras" }

    async fn collect(&self) -> anyhow::Result<OltData> {
        let mut data = self.inner.collect().await?;
        data.olt_id = self.olt_id.clone();
        data.vendor = "intelbras".into();
        Ok(data)
    }

    async fn test_connection(&self) -> anyhow::Result<bool> {
        self.inner.test_connection().await
    }
}
