ALTER TABLE idea ADD COLUMN kind_label TEXT;

UPDATE idea SET
  kind_label = CASE
    WHEN substr(content, 1, 14) = '[observation] ' THEN 'observation'
    WHEN substr(content, 1, 11) = '[decision] '   THEN 'decision'
    WHEN substr(content, 1, 13) = '[assumption] ' THEN 'assumption'
    WHEN substr(content, 1, 11) = '[question] '   THEN 'question'
    WHEN substr(content, 1, 12) = '[next_step] '  THEN 'next_step'
    ELSE NULL
  END,
  content = CASE
    WHEN substr(content, 1, 14) = '[observation] ' THEN substr(content, 15)
    WHEN substr(content, 1, 11) = '[decision] '   THEN substr(content, 12)
    WHEN substr(content, 1, 13) = '[assumption] ' THEN substr(content, 14)
    WHEN substr(content, 1, 11) = '[question] '   THEN substr(content, 12)
    WHEN substr(content, 1, 12) = '[next_step] '  THEN substr(content, 13)
    ELSE content
  END
WHERE kind = 'checkpoint';
