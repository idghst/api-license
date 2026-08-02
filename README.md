# fastapi-license

`license` Supabase schema를 사용하는 라이선스 관리 FastAPI 서비스입니다. Vercel에는
Preview와 Production을 분리합니다. 라이선스 CRUD는 서버 전용 `X-Admin-Key`와
`SUPABASE_SECRET_KEY`를 함께 요구하며, 브라우저의 Supabase 직접 접근은 허용하지
않습니다. 기존 `/api/v1/auth/me`는 Supabase Auth JWT 검증 경로로 유지됩니다.

## Local development

Python 3.12와 [uv](https://docs.astral.sh/uv/)가 필요합니다.

```bash
uv sync --locked --dev
```

`.env.local`을 로컬에만 만들고 실제 키는 절대 커밋하지 마세요. `CORS_ORIGINS`는 JSON
배열이며 `*`를 사용할 수 없습니다.

```dotenv
APP_ENV=development
LOG_LEVEL=INFO
ENABLE_DOCS=true
CORS_ORIGINS=["http://localhost:3000"]
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_PUBLISHABLE_KEY=your_publishable_key
SUPABASE_TIMEOUT_SECONDS=5
# 라이선스 CRUD에 필수. 브라우저와 `NEXT_PUBLIC_` 변수에 절대 노출 금지.
SUPABASE_SECRET_KEY=
# 관리 콘솔 BFF와 이 API만 공유하는 충분히 긴 랜덤 값. 브라우저에 노출 금지.
ADMIN_API_KEY=
```

```bash
uv run uvicorn app.main:app --reload
```

- API: <http://127.0.0.1:8000>
- Docs (development/명시 허용 시): <http://127.0.0.1:8000/docs>
- Liveness: <http://127.0.0.1:8000/health/live>
- Readiness: <http://127.0.0.1:8000/health/ready>

Vercel 런타임을 로컬에서 확인할 때는 Vercel에 연결된 프로젝트의 환경 변수를
가져온 뒤 실행합니다.

```bash
vercel dev
```

## Supabase setup

서비스별로 별도 Supabase 프로젝트를 사용합니다. 이 서비스의 PostgREST 기본
스키마는 `license`이며, `public`에 업무 테이블을 만들지 않습니다.

1. Supabase Dashboard의 **API Settings → Exposed schemas**에 `license`를 추가합니다.
2. 필요한 Preview/Production 프로젝트 각각에 migration을 적용합니다.
3. `license.licenses` migration을 적용합니다. 이 테이블은 RLS를 켜고 `anon`·
   `authenticated` 권한과 정책을 부여하지 않습니다. API의 서버 secret client만
   접근하며, `service_role`/secret key는 이 관리 CRUD 경로에서만 사용합니다.

Supabase CLI를 프로젝트 루트에서 초기화·연결한 뒤 migration을 적용합니다. 실제
project ref와 자격 증명은 CLI 프롬프트 또는 안전한 환경 변수로만 전달합니다.

```bash
npx --yes supabase@latest init
npx --yes supabase@latest link
npx --yes supabase@latest db push
```

`supabase/migrations/`은 순서대로 적용됩니다. 새 migration은 항상 CLI가 생성한
파일에 추가합니다.

```bash
npx --yes supabase@latest migration new describe_change
```

## Auth API check

`/api/v1/auth/me`는 `Authorization: Bearer <Supabase access token>`을 요구합니다.
유효한 JWT가 없으면 표준 오류 envelope와 `401`을 반환합니다.

```bash
curl -i \
  -H 'Authorization: Bearer invalid-token' \
  http://127.0.0.1:8000/api/v1/auth/me
```

정상 요청에는 `id`, `email`만 반환합니다. 오류 응답도 `X-Request-ID`를 반환하므로
장애 문의와 로그 검색에 그 값을 함께 사용하세요.

## License management API

모든 라이선스 관리 요청은 `X-Admin-Key: <ADMIN_API_KEY>`를 요구합니다. 키 누락·오류는
`401`, 서버에 `ADMIN_API_KEY` 또는 `SUPABASE_SECRET_KEY`가 없으면 `503` 오류 envelope를
반환합니다. 관리 콘솔에서는 브라우저가 키를 직접 갖지 않고, 같은 서버의 BFF가 이
헤더를 붙여야 합니다.

| Method | Path | Result |
| --- | --- | --- |
| `GET` | `/api/v1/licenses` | `{ "items": [...], "count": n }` |
| `POST` | `/api/v1/licenses` | 생성된 레코드 (`201`) |
| `PATCH` | `/api/v1/licenses/{id}` | 변경된 레코드 |
| `DELETE` | `/api/v1/licenses/{id}` | `204 No Content` |

레코드는 `id`, `productName`, `vendor`, `totalSeats`, `usedSeats`, `startDate`,
`expiresAt`, `renewalDate`, `status`, `memo`, `createdAt`, `updatedAt`을 사용합니다.
`status`는 `active`, `expiring`, `expired`, `inactive` 중 하나입니다. `usedSeats`는
`totalSeats`를 초과할 수 없고, `expiresAt`은 `startDate`보다 앞설 수 없습니다.

`licenseKey`는 의도적으로 지원하지 않습니다. 평문 또는 암호문 모두 DB/API에 저장·
반환하지 않으며, 해당 필드를 보내면 `422 validation_error`를 반환합니다. 나중에 키
보관이 필요하면 별도 키 관리 설계와 `LICENSE_KEY_ENCRYPTION_KEY` 기반 암호화/마스킹
계약을 먼저 도입해야 합니다.

```bash
curl -i \
  -H 'X-Admin-Key: replace-with-server-only-key' \
  http://127.0.0.1:8000/api/v1/licenses
```

## CI

GitHub Actions는 잠금 파일, 포맷, lint, 타입, 비통합 테스트(coverage 90% 이상),
의존성 취약점을 검사합니다. 캐시 없이 의존성을 설치해 잠금 파일의 재현성을
확인합니다. 로컬에서도 같은 게이트를 실행합니다.

```bash
uv lock --check
uv run ruff format --check app tests
uv run ruff check app tests
uv run mypy app
uv run pytest -m "not integration" --cov=app --cov-report=term-missing
uv run pip-audit
```

통합 테스트는 실제 Supabase Preview 환경을 대상으로 별도로 실행합니다.

```bash
uv run pytest -m integration
```

## Vercel deployment

`vercel.json`은 FastAPI framework preset과 `app/main.py` 함수 진입점을 고정하고,
Fluid Compute와 `maxDuration: 30`을 설정합니다. `.vercelignore`는 root allowlist로
런타임에 필요한 `app/**/*.py`, `pyproject.toml`, `uv.lock`, `.python-version`,
`vercel.json`만 업로드합니다. 그러므로 `tests/`, `docs/`, `supabase/`, `.venv/`는
함수 번들에 포함되지 않습니다.

Vercel Dashboard에서 **같은 `fastapi-license` 프로젝트의** Preview와 Production
환경을 분리해 아래 변수를 모두 설정합니다.

| Variable | Preview | Production | Notes |
| --- | --- | --- | --- |
| `APP_ENV` | `production` | `production` | 배포 런타임은 docs 기본 비활성 |
| `LOG_LEVEL` | `INFO` | `INFO` 또는 `WARNING` | JSON 구조화 로그 |
| `ENABLE_DOCS` | `false` | `false` | 운영 API 스키마 비공개 |
| `CORS_ORIGINS` | Preview UI origin만 | Production UI origin만 | JSON 배열, wildcard 금지 |
| `SUPABASE_URL` | Preview Supabase URL | Production Supabase URL | 서비스별 별도 프로젝트 |
| `SUPABASE_PUBLISHABLE_KEY` | Preview publishable key | Production publishable key | 요청 JWT 검증·RLS 호출 |
| `SUPABASE_TIMEOUT_SECONDS` | `5` | `5` | 양수 초 단위 |
| `SUPABASE_SECRET_KEY` | 서버 전용 | 서버 전용 | 라이선스 CRUD의 Supabase service/secret key |
| `ADMIN_API_KEY` | 서버 전용 | 서버 전용 | 관리 콘솔 BFF와 공유, `X-Admin-Key` 검증용 |

배포 전에 CLI 상태와 build 인자를 확인하고, Vercel 프로젝트
`fastapi-license`을 명시적으로 연결한 뒤 Preview 설정만 가져옵니다. Vercel link는
프로젝트에 연결하는 작업이며, 이 **한 프로젝트** 안에 Preview와 Production 환경 변수
세트를 각각 둡니다. `.vercel/`은 gitignore 대상이므로 연결 정보와 원격 환경 값은
커밋되지 않습니다. 이 runbook은 `--prod`, `vercel promote`, `--prebuilt`를 사용하지
않습니다.

```bash
vercel whoami
vercel build --help
vercel project list --scope idghst
# fastapi-license이 없다면 한 번만 명시적으로 생성
vercel project add fastapi-license --scope idghst
# 새 프로젝트 또는 기존 Other preset을 FastAPI로 맞춤
vercel project update fastapi-license --framework fastapi --scope idghst
vercel link --yes --team idghst --project fastapi-license
vercel pull --environment=preview
# 로컬 호환성 검증 전용. 이 결과물을 배포하지 않습니다.
vercel build --target=preview
# source를 직접 업로드하는 Preview 배포만 사용합니다.
vercel deploy --target=preview
```

로컬 build는 호환성 검증 전용입니다. Vercel CLI의 local build는 source upload 단계의
`.vercelignore` 필터를 적용하지 않으므로, 생성된 `.vercel/output`은 배포하지 말고
검증 후 삭제합니다. deploy는 `.vercelignore` allowlist가 적용되는 direct source
deployment를 사용합니다. 현재 작업 디렉터리에서 `--prebuilt`는 사용하지 않습니다.
배포 후 probe 전에 반환된 URL/ID를
`vercel inspect <preview-url-or-deployment-id> --format=json`으로 확인하고 Target이
Preview인지 검증합니다. Preview 배포가 `/health/ready`에서 `200`을 반환하기 전에는
`vercel promote` 또는 `--prod`를 실행하지 않습니다.

반환된 Preview URL에서 다음 상태를 확인합니다. `/health/ready`가 `503`이면
promotion하지 말고 Supabase URL, publishable key, exposed schema, 네트워크 로그를
점검합니다.

```bash
curl -i https://preview.example.vercel.app/
curl -i https://preview.example.vercel.app/health/live
curl -i https://preview.example.vercel.app/health/ready
curl -i -H 'Authorization: Bearer invalid-token' \
  https://preview.example.vercel.app/api/v1/auth/me
```

기대 상태는 각각 `200`, `200`, `200`, `401`입니다.

## Rollback and incident response

장애 배포는 Vercel Dashboard의 이전 정상 deployment로 rollback하거나, 확인한
deployment URL/ID를 사용해 실행합니다.

```bash
vercel rollback <deployment-url-or-id>
```

장애 조사 순서:

1. 응답의 `X-Request-ID`와 배포 URL을 확보합니다.
2. Vercel Functions 로그에서 같은 request ID를 검색합니다.
3. `500`이면 배포 환경 변수와 import 오류를, `503`이면 Supabase 상태·네트워크·timeout을
   확인합니다.
4. `401`이면 `/auth/me`의 access token 또는 관리 CRUD의 `X-Admin-Key` 전달 여부를
   대조합니다.
5. `403` 또는 빈 결과면 `license`의 exposed schema·RLS·server secret key 설정을
   확인합니다.

키나 JWT 원문은 issue, 로그, 커밋에 넣지 않습니다.
