//! ENLACE RF Engine — gRPC server entry point.
//!
//! Starts a Tonic gRPC server that exposes the RF propagation, coverage,
//! optimization, link budget, and terrain profile services.

mod config;
mod handlers;

/// Generated protobuf types and service traits.
#[allow(unused)]
mod proto {
    tonic::include_proto!("enlace.rf");
}

use tonic::transport::{Identity, Server, ServerTlsConfig};
use tracing_subscriber as _;

use config::ServiceConfig;
use handlers::RfEngineService;
use proto::rf_engine_server::RfEngineServer;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt::init();

    let config = ServiceConfig::default();
    let addr = config.listen_addr.parse()?;

    tracing::info!("ENLACE RF Engine v{}", env!("CARGO_PKG_VERSION"));
    tracing::info!("SRTM tile directory: {}", config.srtm_tile_dir);
    tracing::info!("Listening on {}", addr);

    let service = RfEngineService::new(config.clone());
    let rf_service = RfEngineServer::new(service);

    let mut builder = Server::builder();

    if let (Some(cert_path), Some(key_path)) = (&config.tls_cert, &config.tls_key) {
        let cert = std::fs::read(cert_path)?;
        let key = std::fs::read(key_path)?;
        let identity = Identity::from_pem(cert, key);
        let tls_config = ServerTlsConfig::new().identity(identity);
        tracing::info!("TLS enabled");
        builder
            .tls_config(tls_config)?
            .add_service(rf_service)
            .serve(addr)
            .await?;
    } else {
        tracing::info!("TLS disabled (set TLS_CERT and TLS_KEY to enable)");
        builder
            .add_service(rf_service)
            .serve(addr)
            .await?;
    }

    Ok(())
}
