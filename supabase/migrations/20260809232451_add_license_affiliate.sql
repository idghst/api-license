alter table license.license_records
  add column affiliate text check (affiliate is null or char_length(affiliate) <= 200);
