create table if not exists public.users (
    telegram_id bigint primary key,
    username text,
    first_name text,
    source text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.events (
    id bigserial primary key,
    telegram_id bigint not null,
    event text not null,
    prompt_id text,
    source text,
    meta jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists events_telegram_id_idx on public.events (telegram_id);
create index if not exists events_event_idx on public.events (event);
create index if not exists events_prompt_id_idx on public.events (prompt_id);

create table if not exists public.submissions (
    id bigserial primary key,
    telegram_id bigint not null,
    prompt_id text not null,
    file_id text not null,
    file_type text not null,
    caption text,
    status text not null default 'accepted',
    verification_status text,
    verification_reason text,
    verification_confidence numeric,
    screenshot_url text,
    created_at timestamptz not null default now()
);

create index if not exists submissions_telegram_id_idx on public.submissions (telegram_id);
create index if not exists submissions_prompt_id_idx on public.submissions (prompt_id);
create index if not exists submissions_status_idx on public.submissions (status);

insert into storage.buckets (id, name, public)
values ('screenshots', 'screenshots', true)
on conflict (id) do nothing;
