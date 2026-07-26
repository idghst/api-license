create schema if not exists license;

grant usage on schema license to anon, authenticated, service_role;

alter default privileges in schema license
  grant all on tables to service_role;

alter default privileges in schema license
  grant all on sequences to service_role;

alter default privileges in schema license
  grant execute on routines to service_role;
