# Phase 1.5 — Precondition Gate Script

> **Purpose:** Verify the `demouser` family exists **with enough data** to
> satisfy assertions in `test-cases/`. This skill does NOT seed data — it
> only checks that prerequisite data is present, and **blocks** the run if
> it isn't. Running UI cases against missing/incomplete data produces
> misleading test reports.

> **Why a gate, not a seed:** the login endpoint deliberately returns the
> same `AUTH_INVALID_CREDENTIALS` for "user not found" and "wrong password"
> (anti-enumeration). So we must log in with known credentials. Captcha is
> skipped in non-production environments (docker/dev), so a plain curl works.

> **Envelope:** every API response is wrapped as
> `{"code":"OK","message":"","data":<payload>}`. All `jq` paths below
> extract from `.data`.

## Gate script (bash)

```bash
API="${API_BASE}"            # e.g. http://localhost/api/v1  or  http://localhost:8000/api/v1

# --- 1) Login with known demouser credentials ---
LOGIN=$(curl -s -w "\n%{http_code}" -X POST "$API/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"username":"demouser","password":"DemoPass123"}')
CODE=$(echo "$LOGIN" | tail -1)
BODY=$(echo "$LOGIN" | sed '$d')

if [ "$CODE" != "200" ]; then
  echo "GATE FAIL: demouser login returned HTTP $CODE (body: $BODY)"
  echo "→ demouser account does not exist or credentials differ."
  exit 1
fi

TOKEN=$(echo "$BODY" | jq -r '.data.access_token')
[ -n "$TOKEN" ] && [ "$TOKEN" != "null" ] || { echo "GATE FAIL: no access_token in login response (body: $BODY)"; exit 1; }
AUTH="Authorization: Bearer $TOKEN"

# --- 2) /auth/me — account belongs to a family, role is adult owner ---
ME=$(curl -s -H "$AUTH" "$API/auth/me")
ME_USER=$(echo "$ME" | jq -r '.data.username')
ME_ROLE=$(echo "$ME" | jq -r '.data.role')
ME_FAM=$(echo "$ME" | jq -r '.data.family_id')
if [ "$ME_USER" != "demouser" ] || [ -z "$ME_FAM" ] || [ "$ME_FAM" = "null" ]; then
  echo "GATE FAIL: /auth/me not a valid demouser adult (username=$ME_USER, family_id=$ME_FAM)"
  exit 1
fi
[ "$ME_ROLE" = "owner" ] || [ "$ME_ROLE" = "adult" ] || { echo "GATE FAIL: demouser role=$ME_ROLE (expected owner/adult)"; exit 1; }

# --- 3) /family/members — at least 1 child present (names discovered, not hard-coded) ---
# The docker seed creates 小宝 + 大宝 under demouser, but dev/other deployments
# may have different child display_names (e.g. demochild, 小明). The gate must
# NOT hard-code specific names — it asserts "≥1 child exists" and records the
# actual display_names found, so downstream cases (and the report) use the real
# names. See test-cases/_common.md "Child account names" for the convention.
MEMBERS=$(curl -s -H "$AUTH" "$API/family/members")
# Children have role=="child" and username may be null; display_name is the label.
CHILD_NAMES=$(echo "$MEMBERS" | jq -r '[.data[] | select(.role=="child") | .display_name] | join(",")')
CHILD_COUNT=$(echo "$MEMBERS" | jq -r '[.data[] | select(.role=="child")] | length')
if [ "$CHILD_COUNT" -lt 1 ] 2>/dev/null || [ -z "$CHILD_NAMES" ]; then
  echo "GATE FAIL: demouser family has no child members (child_count=$CHILD_COUNT)"
  exit 1
fi
echo "  (discovered child display_names: $CHILD_NAMES)"

# --- 4) /dashboard/overview — demouser has real asset data (>0) ---
OV=$(curl -s -H "$AUTH" "$API/dashboard/overview")
ASSET_COUNT=$(echo "$OV" | jq -r '.data.asset_count')
TOTAL_LIAB=$(echo "$OV" | jq -r '.data.total_liabilities')
[ "$ASSET_COUNT" -gt 0 ] 2>/dev/null || { echo "GATE FAIL: demouser has no assets (asset_count=$ASSET_COUNT)"; exit 1; }
echo "$TOTAL_LIAB" | awk '{if ($1+0 <= 0) exit 1}' || echo "  (note: demouser has no liabilities — liability cases C2.5/C2.6 may show empty states)"

# --- 5) AI provider check — warn if not configured (Area 3/6 will SKIP-AI) ---
# Correct endpoint: GET /ai/config returns per-family AI provider configs.
# (NOT /ai/config/defaults — that's a form helper that requires model_id query param.)
AI_CONFIGS=$(curl -s -H "$AUTH" "$API/ai/config" 2>/dev/null || echo '{"data":{"configs":[]}}')
AI_ACTIVE=$(echo "$AI_CONFIGS" | jq '[.data.configs[]? | select(.is_active == true)] | length' 2>/dev/null || echo "0")
AI_FIRST_PROVIDER=$(echo "$AI_CONFIGS" | jq -r '.data.configs[0].provider // empty' 2>/dev/null || echo "")
if [ "$AI_ACTIVE" -lt 1 ] 2>/dev/null || [ -z "$AI_FIRST_PROVIDER" ]; then
  echo "  (WARNING: AI provider not configured — Area 3/6 cases will be SKIP-AI)"
else
  echo "  (AI provider: $AI_FIRST_PROVIDER, active configs: $AI_ACTIVE)"
fi

# --- 6) Wish savings data check — warn if no wishes with savings (C2.14 will show empty state) ---
WISHES=$(curl -s -H "$AUTH" "$API/wishes" 2>/dev/null || echo '{"data":[]}')
WISH_SAVINGS=$(echo "$WISHES" | jq '[.data[] | select(.saved_amount != null and .saved_amount != "0" and .saved_amount != "0.00")] | length' 2>/dev/null || echo "0")
if [ "$WISH_SAVINGS" -lt 1 ] 2>/dev/null; then
  echo "  (WARNING: no wishes with savings data — C2.14 savings log will show empty state)"
else
  echo "  (wishes with savings: $WISH_SAVINGS)"
fi

# --- 7) High-interest liability check — warn if none (C2.15 debt hint won't trigger) ---
LIABILITIES=$(curl -s -H "$AUTH" "$API/liabilities" 2>/dev/null || echo '{"data":[]}')
HIGH_RATE=$(echo "$LIABILITIES" | jq '[.data[] | select(.interest_rate != null and (.interest_rate | tonumber) >= 15)] | length' 2>/dev/null || echo "0")
if [ "$HIGH_RATE" -lt 1 ] 2>/dev/null; then
  echo "  (WARNING: no high-interest liabilities (rate ≥ 15%) — C2.15 debt warning hint won't trigger)"
else
  echo "  (high-interest liabilities: $HIGH_RATE)"
fi

# --- 8) Child app auth bootstrap check — warn if child cannot authenticate in dev mode ---
# In dev mode adult (:5173) and child (:5174) are different origins; child app has
# no standalone login pages and redirects to adult login on 401. Verify that the
# child step1/step2 auth endpoints exist and can return a temp_token for the first
# discovered child, so the skill can establish a child session when Phase 5 runs.
FIRST_CHILD_NAME=$(echo "$MEMBERS" | jq -r '[.data[] | select(.role=="child") | .display_name] | first // empty')
FIRST_CHILD_USER=$(echo "$MEMBERS" | jq -r '[.data[] | select(.role=="child") | .username] | first // empty')
CHILD_USERNAME=${FIRST_CHILD_USER:-"$FIRST_CHILD_NAME"}
CHILD_PASSWORD="DemoPass123"
STEP1=$(curl -s -w "\n%{http_code}" -X POST "$API/auth/login/step1" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$CHILD_USERNAME\",\"password\":\"$CHILD_PASSWORD\"}")
STEP1_CODE=$(echo "$STEP1" | tail -1)
STEP1_BODY=$(echo "$STEP1" | sed '$d')
if [ "$STEP1_CODE" != "200" ]; then
  echo "  (WARNING: child auth step1 returned HTTP $STEP1_CODE — Area 1/5 cases will be SKIP-CHILD)"
  echo "    body: $STEP1_BODY"
else
  echo "  (child auth step1 OK for user=$CHILD_USERNAME)"

  # --- 8b) Child auth step2 (emoji PIN) pre-check ---
  # Verify step2 endpoint accepts the temp_token from step1. If step2 fails
  # (e.g. backend PIN config changed), Area 1/5 cases would silently fail at
  # session injection time. Check now so the gate catches it early.
  TEMP_TOKEN=$(echo "$STEP1_BODY" | jq -r '.data.temp_token // empty')
  if [ -n "$TEMP_TOKEN" ]; then
    STEP2=$(curl -s -w "\n%{http_code}" -X POST "$API/auth/login/step2" \
      -H 'Content-Type: application/json' \
      -d "{\"username\":\"$CHILD_USERNAME\",\"temp_token\":\"$TEMP_TOKEN\",\"pin\":\"0000\"}")
    STEP2_CODE=$(echo "$STEP2" | tail -1)
    if [ "$STEP2_CODE" != "200" ] && [ "$STEP2_CODE" != "401" ]; then
      # 401 = wrong PIN (expected, we sent dummy "0000") — endpoint works
      echo "  (WARNING: child auth step2 returned HTTP $STEP2_CODE — emoji PIN endpoint may be misconfigured)"
    else
      echo "  (child auth step2 endpoint OK — emoji PIN flow functional)"
    fi
    unset STEP2 STEP2_CODE TEMP_TOKEN
  fi
fi

# Export CHILD_NAMES for downstream phases/report (single source of truth).
echo "export SIM_CHILD_NAMES=\"$CHILD_NAMES\""
echo "GATE OK: demouser family present with $CHILD_COUNT child(ren) [$CHILD_NAMES] and $ASSET_COUNT assets."

# --- 9) Token cleanup — do not leave auth material in shell environment ---
unset LOGIN BODY ME ME_USER ME_ROLE ME_FAM MEMBERS CHILD_COUNT OV ASSET_COUNT TOTAL_LIAB
unset AI_CONFIGS AI_ACTIVE WISHES WISH_SAVINGS LIABILITIES HIGH_RATE
unset STEP1 STEP1_CODE STEP1_BODY FIRST_CHILD_NAME FIRST_CHILD_USER CHILD_USERNAME CHILD_PASSWORD
# Keep TOKEN and AUTH for subsequent phases; unset after Phase 5 cleanup.
```

## Gate failure → block

If any check fails, **do not proceed to Phase 2**. Tell the user:

> Precondition check failed: `<specific failure>`.
> The `demouser` family is missing or its data is incomplete — this skill does
> not seed data. Prepare the database out-of-band, then re-run:
>   `./tests/data/seed-data.sh`   (docker: inside the `numina-backend` container; dev: local `uv run`)
> Verify `demouser`/`DemoPass123` exists with at least 1 child member and
> assets before retrying. Child display_names are discovered at gate time
> (not hard-coded) — see `test-cases/_common.md`.

> **Liabilities are soft.** `demouser`'s seed profile includes liabilities, but
> if only liabilities are missing (assets + children present), the gate still
> passes and liability cases (C2.5/C2.6) will simply show empty states — note
> this in the report rather than blocking.
