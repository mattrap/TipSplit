-- 1) Main access table
create table if not exists public.access_policies (
  user_id uuid references auth.users(id) on delete cascade,
  status text not null default 'active' check (status in ('active','blocked','expired')),
  role text not null default 'user' check (role in ('admin','manager','user')),
  expires_at timestamptz,
  revocation_version integer not null default 0,
  updated_at timestamptz not null default now(),
  primary key (user_id)
);

-- 2) Global control flags
create table if not exists public.control_flags (
  id int primary key default 1,
  min_client_version text,
  global_lock boolean not null default false,
  updated_at timestamptz not null default now()
);

insert into public.control_flags (id)
values (1)
on conflict (id) do nothing;

-- 3) Security (RLS)
alter table public.access_policies enable row level security;

create policy "user can read own policy"
on public.access_policies
for select
to authenticated
using (auth.uid() = user_id);

alter table public.control_flags enable row level security;

create policy "any auth can read control_flags"
on public.control_flags
for select
to authenticated
using (true);
