create table if not exists public.users (
    telegram_id bigint primary key,
    username text,
    first_name text,
    source text,
    active_campaign_id bigint,
    role text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.users add column if not exists active_campaign_id bigint;
alter table public.users add column if not exists role text;

create table if not exists public.events (
    id bigserial primary key,
    telegram_id bigint not null,
    event text not null,
    prompt_id text,
    campaign_id bigint,
    source text,
    meta jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

alter table public.events add column if not exists campaign_id bigint;

create index if not exists events_telegram_id_idx on public.events (telegram_id);
create index if not exists events_event_idx on public.events (event);
create index if not exists events_prompt_id_idx on public.events (prompt_id);
create index if not exists events_campaign_id_idx on public.events (campaign_id);

create table if not exists public.campaigns (
    id bigint primary key,
    creator_id bigint,
    title text,
    niche text,
    audience text,
    goal text,
    platform text,
    post_text text,
    cta text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.campaign_prompts (
    id bigserial primary key,
    campaign_id bigint not null,
    prompt_key text not null,
    title text not null,
    short text,
    prompt_text text not null,
    sort_order integer,
    created_at timestamptz not null default now()
);

create index if not exists campaign_prompts_campaign_id_idx on public.campaign_prompts (campaign_id);
create unique index if not exists campaign_prompts_campaign_key_idx on public.campaign_prompts (campaign_id, prompt_key);

create table if not exists public.submissions (
    id bigserial primary key,
    telegram_id bigint not null,
    campaign_id bigint,
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

alter table public.submissions add column if not exists campaign_id bigint;
alter table public.submissions add column if not exists verification_status text;
alter table public.submissions add column if not exists verification_reason text;
alter table public.submissions add column if not exists verification_confidence numeric;
alter table public.submissions add column if not exists screenshot_url text;

update public.users set active_campaign_id = 1 where active_campaign_id is null;
update public.events set campaign_id = 1 where campaign_id is null;
update public.submissions set campaign_id = 1 where campaign_id is null;

create index if not exists submissions_telegram_id_idx on public.submissions (telegram_id);
create index if not exists submissions_prompt_id_idx on public.submissions (prompt_id);
create index if not exists submissions_status_idx on public.submissions (status);

insert into storage.buckets (id, name, public)
values ('screenshots', 'screenshots', true)
on conflict (id) do nothing;
