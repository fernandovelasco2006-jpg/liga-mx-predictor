-- Migración nov/2026: auto calibración sobre datos limpios.
-- Correr una vez en el SQL Editor de Supabase (proyecto Liga MX).
-- Hasta que se corra, la app sigue guardando sin estas columnas, pero la
-- isotónica y el sesgo por equipo no tienen filas de la versión actual
-- y se quedan apagados (se usa la confianza cruda tal cual).

ALTER TABLE predicciones_ligamx
    ADD COLUMN IF NOT EXISTS version_modelo text;

ALTER TABLE apuestas_historial_ligamx
    ADD COLUMN IF NOT EXISTS version_modelo text,
    ADD COLUMN IF NOT EXISTS confianza_cruda numeric;
