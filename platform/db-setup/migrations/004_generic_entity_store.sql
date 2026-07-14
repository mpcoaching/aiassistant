-- +goose Up
-- Add the business identifier column
ALTER TABLE generic_entity_store 
ADD COLUMN entity_key VARCHAR(255);

-- Create a composite unique index for upsert performance
CREATE UNIQUE INDEX idx_generic_entity_store_lookup 
ON generic_entity_store (tenant_id, entity_type, entity_key);

-- +goose StatementBegin
-- Procedure for Upsert
CREATE OR REPLACE FUNCTION upsert_generic_entity(
    p_tenant_id VARCHAR,
    p_entity_type VARCHAR,
    p_entity_key VARCHAR,
    p_data JSONB
) RETURNS VOID AS $$
BEGIN
    INSERT INTO generic_entity_store (tenant_id, entity_type, entity_key, data_json, updated_at)
    VALUES (p_tenant_id, p_entity_type, p_entity_key, p_data, CURRENT_TIMESTAMP)
    ON CONFLICT (tenant_id, entity_type, entity_key)
    DO UPDATE SET 
        data_json = EXCLUDED.data_json,
        updated_at = CURRENT_TIMESTAMP;
END;
$$ LANGUAGE plpgsql;
-- +goose StatementEnd

-- +goose StatementBegin
-- Procedure for Deletion
CREATE OR REPLACE FUNCTION delete_generic_entity(
    p_tenant_id VARCHAR,
    p_entity_type VARCHAR,
    p_entity_key VARCHAR
) RETURNS VOID AS $$
BEGIN
    DELETE FROM generic_entity_store 
    WHERE tenant_id = p_tenant_id 
      AND entity_type = p_entity_type 
      AND entity_key = p_entity_key;
END;
$$ LANGUAGE plpgsql;
-- +goose StatementEnd

-- +goose StatementBegin
-- Procedure to fetch a generic entity as JSONB
CREATE OR REPLACE FUNCTION get_entity(
    p_tenant_id VARCHAR,
    p_entity_type VARCHAR,
    p_entity_key VARCHAR
) RETURNS JSONB AS $$
DECLARE
    v_data JSONB;
BEGIN
    SELECT data_json INTO v_data
    FROM generic_entity_store
    WHERE tenant_id = p_tenant_id 
      AND entity_type = p_entity_type 
      AND entity_key = p_entity_key;
    
    RETURN v_data;
END;
$$ LANGUAGE plpgsql;
-- +goose StatementEnd

-- +goose Down
DROP FUNCTION IF EXISTS get_entity;
DROP FUNCTION IF EXISTS delete_generic_entity;
DROP FUNCTION IF EXISTS upsert_generic_entity;
DROP INDEX IF EXISTS idx_generic_entity_store_lookup;
ALTER TABLE generic_entity_store DROP COLUMN entity_key;