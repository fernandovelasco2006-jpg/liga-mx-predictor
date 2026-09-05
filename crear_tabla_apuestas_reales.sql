-- Tabla para trackear apuestas REALES colocadas con dinero real en una
-- casa de apuestas externa (PlayDoit, Caliente, etc.), basadas en las
-- recomendaciones del modelo — separada de apuestas_historial_ligamx
-- (que registra TODAS las sugerencias del modelo, se hayan apostado o
-- no). Esta tabla es la fuente de verdad para calcular ROI real en
-- dinero, no solo Brier Score/accuracy de probabilidad.

create table if not exists apuestas_reales_ligamx (
    id text primary key,
    id_boleto_casa text,              -- ID del boleto en la casa de apuestas (ej. "5377426236")
    casa text not null,               -- "PlayDoit", "Caliente", etc.
    fecha date not null,
    tipo text not null,               -- "individual", "sgp", "parlay"
    selecciones jsonb not null,       -- lista de {local, visitante, mercado, seleccion}
    momio numeric not null,           -- cuota decimal final del boleto completo
    monto_apostado numeric not null,  -- en MXN
    resultado text default 'pendiente', -- "ganado", "perdido", "pendiente"
    ganancia_neta numeric,            -- se calcula al resolver: (monto*momio - monto) si ganó, -monto si perdió
    creado_en timestamp default now()
);

-- Row Level Security básico (ajustar según tu configuración existente
-- en las otras tablas *_ligamx)
alter table apuestas_reales_ligamx enable row level security;

create policy "Permitir todo con anon key" on apuestas_reales_ligamx
    for all using (true) with check (true);
