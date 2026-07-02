// SPDX-License-Identifier: Apache-2.0
// Minimal sd_notify(3) implementation — hand-rolled unix-datagram writer so
// the agent can run under `Type=notify` with `WatchdogSec=` without pulling
// in libsystemd. Everything here is a no-op when NOTIFY_SOCKET is unset
// (CLI runs, containers, non-systemd inits).

use std::os::unix::net::UnixDatagram;
use tracing::{debug, warn};

/// Send a state string ("READY=1", "WATCHDOG=1", "STOPPING=1", ...) to the
/// systemd notification socket. No-op when NOTIFY_SOCKET is unset; failures
/// are logged, never fatal.
pub fn notify(state: &str) {
    let Ok(path) = std::env::var("NOTIFY_SOCKET") else {
        return;
    };
    if let Err(e) = send_to_notify_socket(&path, state) {
        warn!(error = %e, state, "sd_notify send failed");
    }
}

fn send_to_notify_socket(path: &str, state: &str) -> std::io::Result<()> {
    let sock = UnixDatagram::unbound()?;
    if let Some(name) = path.strip_prefix('@') {
        // Abstract-namespace socket (leading '@' per sd_notify(3))
        use std::os::linux::net::SocketAddrExt;
        let addr = std::os::unix::net::SocketAddr::from_abstract_name(name.as_bytes())?;
        sock.send_to_addr(state.as_bytes(), &addr)?;
    } else {
        sock.send_to(state.as_bytes(), path)?;
    }
    Ok(())
}

/// Spawn the watchdog keep-alive task when systemd requested one
/// (WATCHDOG_USEC set, WATCHDOG_PID absent or matching this process).
/// Pings at half the configured watchdog interval, as recommended by
/// sd_watchdog_enabled(3).
pub fn spawn_watchdog() -> Option<tokio::task::JoinHandle<()>> {
    if std::env::var("NOTIFY_SOCKET").is_err() {
        return None;
    }
    let usec: u64 = std::env::var("WATCHDOG_USEC").ok()?.parse().ok()?;
    if usec == 0 {
        return None;
    }
    if let Ok(pid) = std::env::var("WATCHDOG_PID") {
        if pid != std::process::id().to_string() {
            debug!(watchdog_pid = %pid, "WATCHDOG_PID is for another process, not pinging");
            return None;
        }
    }

    let interval = std::time::Duration::from_micros(usec / 2)
        .max(std::time::Duration::from_secs(1));
    debug!(
        watchdog_usec = usec,
        ping_interval_secs = interval.as_secs(),
        "systemd watchdog enabled, starting keep-alive pings"
    );
    Some(tokio::spawn(async move {
        let mut tick = tokio::time::interval(interval);
        tick.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);
        loop {
            tick.tick().await;
            notify("WATCHDOG=1");
        }
    }))
}

/// Handle SIGHUP gracefully: config reload is not supported, so log and keep
/// running instead of dying (the default SIGHUP action terminates, which
/// turned `systemctl reload` into a kill).
pub fn spawn_sighup_handler() -> tokio::task::JoinHandle<()> {
    tokio::spawn(async {
        let mut sighup = match tokio::signal::unix::signal(
            tokio::signal::unix::SignalKind::hangup(),
        ) {
            Ok(s) => s,
            Err(e) => {
                warn!(error = %e, "Failed to install SIGHUP handler");
                return;
            }
        };
        loop {
            if sighup.recv().await.is_none() {
                return;
            }
            warn!("SIGHUP received — config reload not supported; restart the service to apply config changes");
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn notify_is_noop_without_socket() {
        // Must not panic or error when NOTIFY_SOCKET is unset.
        std::env::remove_var("NOTIFY_SOCKET");
        notify("READY=1");
    }

    #[test]
    fn notify_delivers_to_unix_datagram_socket() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("notify.sock");
        let server = UnixDatagram::bind(&path).unwrap();

        send_to_notify_socket(path.to_str().unwrap(), "READY=1").unwrap();

        let mut buf = [0u8; 64];
        let n = server.recv(&mut buf).unwrap();
        assert_eq!(&buf[..n], b"READY=1");
    }
}
