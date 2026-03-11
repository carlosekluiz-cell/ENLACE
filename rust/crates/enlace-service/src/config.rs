//! Service configuration loaded from environment variables.

/// Configuration for the ENLACE RF Engine gRPC service.
#[derive(Debug, Clone)]
pub struct ServiceConfig {
    /// Network address to bind the gRPC server to.
    pub listen_addr: String,
    /// Directory containing SRTM HGT elevation tiles.
    pub srtm_tile_dir: String,
    /// Maximum number of SRTM tiles to keep in LRU cache.
    pub tile_cache_size: usize,
    /// Path to TLS certificate file (PEM). If set, enables TLS.
    pub tls_cert: Option<String>,
    /// Path to TLS private key file (PEM).
    pub tls_key: Option<String>,
}

impl Default for ServiceConfig {
    fn default() -> Self {
        Self {
            listen_addr: std::env::var("RF_ENGINE_ADDR")
                .unwrap_or_else(|_| "0.0.0.0:50051".into()),
            srtm_tile_dir: std::env::var("SRTM_TILE_DIR")
                .unwrap_or_else(|_| "/data/srtm".into()),
            tile_cache_size: 50,
            tls_cert: std::env::var("TLS_CERT").ok(),
            tls_key: std::env::var("TLS_KEY").ok(),
        }
    }
}
