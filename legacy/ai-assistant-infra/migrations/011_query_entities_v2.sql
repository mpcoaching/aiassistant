-- +goose Up
-- +goose StatementBegin
CREATE OR REPLACE FUNCTION query_entities(
    p_tenant_id VARCHAR,
    p_entity_type VARCHAR DEFAULT NULL,
    p_taxonomy_filter TEXT[] DEFAULT NULL
) RETURNS TABLE(entity_type VARCHAR, entity_key VARCHAR, data_json JSONB) AS $$
BEGIN
    RETURN QUERY
    SELECT s.entity_type, s.entity_key, s.data_json
    FROM generic_entity_store s
    WHERE s.tenant_id = p_tenant_id
      -- Filter by entity_type if provided
      AND (p_entity_type IS NULL OR s.entity_type = p_entity_type)
      -- Filter by taxonomy if provided (matches ANY in the array)
      AND (p_taxonomy_filter IS NULL OR p_taxonomy_filter = '{}' OR s.data_json->>'taxonomy' = ANY(p_taxonomy_filter));
END;
$$ LANGUAGE plpgsql;
-- +goose StatementEnd

-- +goose Down
DROP FUNCTION IF EXISTS query_entities;