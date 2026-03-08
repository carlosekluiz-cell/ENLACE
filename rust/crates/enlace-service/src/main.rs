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

use tonic::transport::Server;
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

    let service = RfEngineService::new(config);

    Server::builder()
        .add_service(RfEngineServer::new(service))
        .serve(addr)
        .await?;

    Ok(())
}
