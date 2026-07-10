-- Migration 0006: LGPD Due Diligence Access Control
-- Adds pessoa natural detection columns and audit logging for DD access.

-- LGPD columns on provider_details
ALTER TABLE provider_details ADD COLUMN IF NOT EXISTS natureza_juridica_codigo INTEGER;
ALTER TABLE provider_details ADD COLUMN IF NOT EXISTS is_pessoa_natural BOOLEAN DEFAULT false;
CREATE INDEX IF NOT EXISTS idx_pd_pessoa_natural ON provider_details(is_pessoa_natural);

-- Due diligence audit log
CREATE TABLE IF NOT EXISTS due_diligence_audit_log (
    id SERIAL PRIMARY KEY,
    buyer_user_id VARCHAR(100) NOT NULL,
    buyer_email VARCHAR(255) NOT NULL,
    buyer_tenant_id VARCHAR(100) NOT NULL,
    target_provider_id INTEGER NOT NULL REFERENCES providers(id),
    target_cnpj VARCHAR(20),
    purpose VARCHAR(500),
    nda_accepted BOOLEAN NOT NULL DEFAULT false,
    data_sections_accessed TEXT[],
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_dd_audit_target ON due_diligence_audit_log(target_provider_id);
CREATE INDEX IF NOT EXISTS idx_dd_audit_tenant ON due_diligence_audit_log(buyer_tenant_id);
CREATE INDEX IF NOT EXISTS idx_dd_audit_created ON due_diligence_audit_log(created_at);
