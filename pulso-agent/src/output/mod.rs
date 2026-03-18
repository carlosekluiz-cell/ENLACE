// SPDX-License-Identifier: Apache-2.0
// Output dispatchers — Elasticsearch, webhooks, and cloud transport

pub mod elastic;
pub mod webhook;

pub use elastic::ElasticOutput;
pub use webhook::WebhookDispatcher;
