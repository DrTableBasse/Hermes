-- Migration 014 : grades charcutiers (palier de niveau → grade affiché sur le site et par le bot)
-- Exécuter manuellement : psql -U <user> -d <db> -f 014_grades.sql

CREATE TABLE IF NOT EXISTS grades (
    id         SERIAL PRIMARY KEY,
    level_min  INT  UNIQUE NOT NULL,
    name       TEXT NOT NULL,
    slug       TEXT UNIQUE NOT NULL,
    color      TEXT NOT NULL
);

INSERT INTO grades (level_min, name, slug, color) VALUES
    (1,  'Recrue Cocktail',      'recrue',     '#9A97B8'),
    (3,  'Caporal Chipolata',    'caporal',    '#3BD16F'),
    (8,  'Sergent Merguez',      'sergent',    '#FF8A3D'),
    (15, 'Lieutenant Toulouse',  'lieutenant', '#4D7CFF'),
    (25, 'Colonel Saucisson',    'colonel',    '#3FE0F0'),
    (45, 'Général Saucisse',     'general',    '#9B6BFF')
ON CONFLICT (level_min) DO NOTHING;
