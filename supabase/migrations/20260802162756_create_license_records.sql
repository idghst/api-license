create table license.license_records (
  id uuid primary key default gen_random_uuid(),
  product_name text not null check (char_length(btrim(product_name)) between 1 and 200),
  vendor text not null check (char_length(btrim(vendor)) between 1 and 200),
  total_seats integer not null check (total_seats >= 1 and total_seats <= 1000000),
  used_seats integer not null check (used_seats >= 0 and used_seats <= total_seats),
  start_date date,
  expires_at date,
  renewal_date date,
  status text not null default 'active' check (status in ('active', 'expiring', 'expired', 'inactive')),
  memo text check (memo is null or char_length(memo) <= 5000),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (expires_at is null or start_date is null or expires_at >= start_date)
);

alter table license.license_records enable row level security;

revoke usage on schema license from anon, authenticated;
grant usage on schema license to service_role;
revoke all privileges on table license.license_records from anon, authenticated;
grant select, insert, update, delete on table license.license_records to service_role;
