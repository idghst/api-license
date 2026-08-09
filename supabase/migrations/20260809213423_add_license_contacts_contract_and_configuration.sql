alter table license.license_records
  add column partnership_contact text check (partnership_contact is null or char_length(partnership_contact) <= 200),
  add column business_contact text check (business_contact is null or char_length(business_contact) <= 200),
  add column contract_contact text check (contract_contact is null or char_length(contract_contact) <= 200),
  add column license_configuration text check (license_configuration is null or char_length(license_configuration) <= 5000);

-- 기존 메모의 구조화된 값은 새 독립 필드로 옮긴다. 자유 형식 메모는 데이터 보존을 위해 유지한다.
update license.license_records
set
  partnership_contact = coalesce(
    partnership_contact,
    nullif(btrim((regexp_match(memo, '(?m)^\[제휴 담당자\][[:space:]]*([^\r\n]+)'))[1]), '')
  ),
  business_contact = coalesce(
    business_contact,
    nullif(btrim((regexp_match(memo, '(?m)^\[사업 담당자\][[:space:]]*([^\r\n]+)'))[1]), '')
  ),
  contract_contact = coalesce(
    contract_contact,
    nullif(btrim((regexp_match(memo, '(?m)^\[계약 담당자\][[:space:]]*([^\r\n]+)'))[1]), '')
  ),
  expires_at = coalesce(
    expires_at,
    ((regexp_match(memo, '(?m)^\[계약 만료일\][[:space:]]*(\d{4}-\d{2}-\d{2})'))[1])::date
  ),
  license_configuration = coalesce(
    license_configuration,
    nullif(btrim((regexp_match(memo, '(?s)\[라이선스 구성\][[:space:]]*(.*)$'))[1]), '')
  ),
  memo = nullif(
    btrim(regexp_replace(memo, '(?m)^\[기존 상태 코드\][^\r\n]*(?:\r?\n)?', '', 'g')),
    ''
  )
where memo is not null;
