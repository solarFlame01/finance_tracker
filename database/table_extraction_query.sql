-- Esporta DDL di tutte le tabelle
SELECT string_agg(
  'CREATE TABLE IF NOT EXISTS ' || tablename || ' (' || 
  array_to_string(ARRAY(
    SELECT column_name || ' ' || data_type || 
    CASE WHEN is_nullable = 'NO' THEN ' NOT NULL' ELSE '' END
    FROM information_schema.columns 
    WHERE table_name = t.tablename
  ), ', ') || ');',
  E'\n\n'
)
FROM pg_tables t
WHERE schemaname = 'public';
