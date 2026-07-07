-- +goose Up
-- +goose StatementBegin
-- Function to fetch multiple entities by a list of types
CREATE OR REPLACE FUNCTION get_entities_by_types(
    p_tenant_id VARCHAR,
    p_entity_types TEXT -- e.g., 'pricing,offer,strategy'
) RETURNS TABLE(entity_type VARCHAR, entity_key VARCHAR, data_json JSONB) AS $$
BEGIN
    RETURN QUERY
    SELECT s.entity_type, s.entity_key, s.data_json
    FROM generic_entity_store s
    WHERE s.tenant_id = p_tenant_id
      AND s.entity_type = ANY(string_to_array(p_entity_types, ','));
END;
$$ LANGUAGE plpgsql;
-- +goose StatementEnd

-- +goose Down
DROP FUNCTION IF EXISTS get_entities_by_types;