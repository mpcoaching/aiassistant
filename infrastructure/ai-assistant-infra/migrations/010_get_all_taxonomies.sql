-- +goose Up
-- +goose StatementBegin
CREATE OR REPLACE FUNCTION get_all_taxonomies(p_tenant_id VARCHAR) 
RETURNS TABLE(taxonomy_type TEXT) AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT s.data_json->>'taxonomy'
    FROM generic_entity_store s
    WHERE s.tenant_id = p_tenant_id
      AND s.data_json ? 'taxonomy';
END;
$$ LANGUAGE plpgsql;
-- +goose StatementEnd

-- +goose Down
DROP FUNCTION IF EXISTS get_all_taxonomies;