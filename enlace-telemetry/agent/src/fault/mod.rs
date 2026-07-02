// SPDX-License-Identifier: Apache-2.0
// Fault Location Engine — detect trunk fibre cuts, estimate break location

pub mod detector;
pub mod topology;
pub mod locator;

pub use detector::{FaultDetector, FaultEvent, FaultType, AffectedOnt};
pub use topology::FibreTopology;
pub use locator::{FaultLocator, FaultLocation};
