-- Esporta DDL di Tabelle + Viste
-- Esegui nel SQL Editor di Supabase

WITH table_ddl AS (
  -- TABELLE
  SELECT 
    'TABLE' as tipo,
    t.tablename,
    'CREATE TABLE IF NOT EXISTS ' || t.tablename || ' (' || 
    string_agg(
      '  ' || c.column_name || ' ' || c.data_type || 
      CASE WHEN c.is_nullable = 'NO' THEN ' NOT NULL' ELSE '' END ||
      CASE WHEN c.column_default IS NOT NULL THEN ' DEFAULT ' || c.column_default ELSE '' END,
      E',\n'
      ORDER BY c.ordinal_position
    ) || E'\n);' as ddl
  FROM pg_tables t
  LEFT JOIN information_schema.columns c 
    ON t.tablename = c.table_name 
    AND t.schemaname = c.table_schema
  WHERE t.schemaname = 'public'
  GROUP BY t.tablename
),

view_ddl AS (
  -- VISTE
  SELECT 
    'VIEW' as tipo,
    v.table_name as tablename,
    'CREATE OR REPLACE VIEW ' || v.table_name || ' AS ' || v.view_definition || ';' as ddl
  FROM information_schema.views v
  WHERE v.table_schema = 'public'
)

-- Output combinato
SELECT tipo, tablename, ddl
FROM table_ddl
UNION ALL
SELECT tipo, tablename, ddl
FROM view_ddl
ORDER BY tipo DESC, tablename;
