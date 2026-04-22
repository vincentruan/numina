# Family Invitation Code Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add invitation code requirement for family creation to control access during launch.

**Architecture:** Single-use 6-character codes stored in dedicated table with full audit trail. Backend validates on register, frontend adds input field, admin script manages code generation/revocation.

**Tech Stack:** FastAPI + SQLAlchemy + Alembic (backend), Vue 3 + Vant 4 (frontend), pytest (testing)

---

## Task 1: Create FamilyInvitationCode Model

**Files:**
- Create: `backend/app/models/family_invitation_code.py`
- Modify: `backend/alembic/env.py:23-24` (import new model)

- [ ] **Step 1: Write the model file**

Create `backend/app/models/family_invitation_code.py`:

```python
"""Family invitation code model for launch control.

Each code can only be used once to create a family.
Complete audit trail: tracks who used it, when, and for which family.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FamilyInvitationCode(Base):
    """Family creation invitation code for launch control.

    Each code can only be used once to create a family.
    Complete audit trail: tracks who used it, when, and for which family.
    Admins can revoke unused codes to invalidate them.
    """

    __tablename__ = "family_invitation_codes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    code: Mapped[str] = mapped_column(
        String(6), unique=True, nullable=False, index=True
    )
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    used_by_family_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("families.id"), nullable=True
    )
    used_by_username: Mapped[str | None] = mapped_column(String(50), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
```

- [ ] **Step 2: Add model import to Alembic env**

Modify `backend/alembic/env.py` line 24 (after other model imports):

```python
from app.models.child_bind_token import ChildBindToken  # noqa: F401
from app.models.family_invitation_code import FamilyInvitationCode  # noqa: F401  # NEW
```

- [ ] **Step 3: Commit model creation**

```bash
cd backend
git add app/models/family_invitation_code.py alembic/env.py
git commit -m "feat(models): add FamilyInvitationCode model for launch control

- Dedicated table for family creation invitation codes
- Single-use 6-character alphanumeric codes
- Full audit trail: family_id, username, timestamp
- Revocation support for unused codes

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Add New Error Codes

**Files:**
- Modify: `backend/app/errors/codes.py:21-22, 148-149`

- [ ] **Step 1: Add 3 new error codes to ErrorCode enum**

Modify `backend/app/errors/codes.py` after line 21 (after `AUTH_WEBAUTHN_VERIFICATION_FAILED`):

```python
    AUTH_WEBAUTHN_VERIFICATION_FAILED = "AUTH_WEBAUTHN_VERIFICATION_FAILED"

    # Family invitation code (NEW)
    FAMILY_INVITATION_CODE_NOT_FOUND = "FAMILY_INVITATION_CODE_NOT_FOUND"
    FAMILY_INVITATION_CODE_ALREADY_USED = "FAMILY_INVITATION_CODE_ALREADY_USED"
    FAMILY_INVITATION_CODE_REVOKED = "FAMILY_INVITATION_CODE_REVOKED"

    # Captcha
```

- [ ] **Step 2: Add HTTP status mappings to ERROR_META**

Modify `backend/app/errors/codes.py` after line 105 (after `AUTH_WEBAUTHN_VERIFICATION_FAILED` entry):

```python
    ErrorCode.AUTH_WEBAUTHN_VERIFICATION_FAILED: 401,
    ErrorCode.FAMILY_INVITATION_CODE_NOT_FOUND: 400,  # NEW
    ErrorCode.FAMILY_INVITATION_CODE_ALREADY_USED: 400,  # NEW
    ErrorCode.FAMILY_INVITATION_CODE_REVOKED: 400,  # NEW
    ErrorCode.CAPTCHA_MISSING: 400,
```

- [ ] **Step 3: Commit error codes**

```bash
cd backend
git add app/errors/codes.py
git commit -m "feat(errors): add family invitation code error codes

- FAMILY_INVITATION_CODE_NOT_FOUND (400)
- FAMILY_INVITATION_CODE_ALREADY_USED (400)
- FAMILY_INVITATION_CODE_REVOKED (400)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Update RegisterRequest Schema

**Files:**
- Modify: `backend/app/schemas/auth.py:40-56`

- [ ] **Step 1: Add family_invitation_code field to RegisterRequest**

Modify `backend/app/schemas/auth.py` line 40-46:

```python
class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str
    family_name: str
    family_invitation_code: str  # NEW: required for family creation
    altcha: str | None = None  # Captcha payload (required in production)

    @field_validator("username")
    @classmethod
    def check_username(cls, v: str) -> str:
        return validate_username(v)

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return validate_password_strength(v)

    @field_validator("family_invitation_code")
    @classmethod
    def normalize_invitation_code(cls, v: str) -> str:
        """Normalize to uppercase for consistent matching."""
        return v.upper().strip()
```

- [ ] **Step 2: Commit schema change**

```bash
cd backend
git add app/schemas/auth.py
git commit -m "feat(schemas): add family_invitation_code to RegisterRequest

- Required field for family creation
- Auto-normalized to uppercase on validation

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Add Validation Logic to register()

**Files:**
- Modify: `backend/app/services/auth.py:273-327`

- [ ] **Step 1: Add import for FamilyInvitationCode**

Modify `backend/app/services/auth.py` line 28 (after User import):

```python
from app.models.user import User
from app.models.family_invitation_code import FamilyInvitationCode  # NEW
```

- [ ] **Step 2: Add invitation code validation in register()**

Modify `backend/app/services/auth.py` lines 273-327. Replace the existing `register()` function:

```python
def register(
    db: Session, req: RegisterRequest, client_ip: str = "unknown"
) -> TokenResponse:
    """Register a new user with invitation code validation.

    Args:
        db: Database session
        req: Registration request
        client_ip: Client IP for rate limiting

    Returns:
        TokenResponse with access and refresh tokens
    """
    # Check registration rate limit
    _check_register_rate_limit(client_ip)

    # Validate family invitation code (NEW)
    invitation_code = (
        db.query(FamilyInvitationCode)
        .filter(FamilyInvitationCode.code == req.family_invitation_code)
        .first()
    )

    if not invitation_code:
        raise AppError(ErrorCode.FAMILY_INVITATION_CODE_NOT_FOUND)

    if invitation_code.is_used:
        raise AppError(ErrorCode.FAMILY_INVITATION_CODE_ALREADY_USED)

    if invitation_code.revoked_at is not None:
        raise AppError(ErrorCode.FAMILY_INVITATION_CODE_REVOKED)

    if db.query(User).filter(User.username == req.username).first():
        raise AppError(ErrorCode.AUTH_USERNAME_EXISTS)

    family_id = str(uuid4())
    user_id = str(uuid4())

    family = Family(
        id=family_id,
        name=req.family_name,
        created_by=user_id,
    )
    db.add(family)

    user = User(
        id=user_id,
        family_id=family_id,
        username=req.username,
        display_name=req.display_name,
        password_hash=hash_password(req.password),
        role="owner",
    )
    db.add(user)

    # Mark invitation code as used (NEW)
    invitation_code.is_used = True
    invitation_code.used_at = datetime.now(UTC).replace(tzinfo=None)
    invitation_code.used_by_family_id = family_id
    invitation_code.used_by_username = req.username

    db.commit()

    # Record successful registration for rate limiting
    _record_register_attempt(client_ip)
    _log_security_event(
        SecurityEventType.REGISTER_SUCCESS, username=req.username, user_id=user_id
    )

    return TokenResponse(
        access_token=create_access_token(
            {"sub": user.id, "fid": user.family_id, "role": user.role}
        ),
        refresh_token=create_refresh_token(
            {"sub": user.id, "fid": user.family_id, "role": user.role}
        ),
    )
```

Note: Need to add `from datetime import datetime, UTC, timedelta` at top of file if not already present.

- [ ] **Step 3: Check UTC import exists**

Check if `datetime, UTC` are imported in `backend/app/services/auth.py`. If not, add to imports:

```python
from datetime import datetime, timedelta, UTC
```

- [ ] **Step 4: Commit service changes**

```bash
cd backend
git add app/services/auth.py
git commit -m "feat(auth): validate family invitation code on register

- Check code exists, not used, not revoked
- Mark code as used after successful registration
- Track family_id and username for audit trail

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Create Database Migration

**Files:**
- Create: `backend/alembic/versions/xxx_add_family_invitation_code.py`

- [ ] **Step 1: Generate Alembic migration**

```bash
cd backend
uv run alembic revision --autogenerate -m "add_family_invitation_code_table"
```

Expected output:
```
Generating /path/to/backend/alembic/versions/xxx_add_family_invitation_code.py ... done
```

- [ ] **Step 2: Review generated migration**

Read the generated migration file and verify it contains:
- `op.create_table('family_invitation_codes', ...)`
- All 8 columns: id, code, is_used, used_at, used_by_family_id, used_by_username, revoked_at, created_at
- `op.create_index('ix_family_invitation_codes_code', ...)`
- `op.create_foreign_key` for used_by_family_id -> families.id

- [ ] **Step 3: Apply migration**

```bash
cd backend
uv run alembic upgrade head
```

Expected output:
```
Running upgrade ... -> xxx, add_family_invitation_code_table
```

- [ ] **Step 4: Verify table creation**

```bash
cd backend
uv run python -c "
from app.database import SessionLocal
from sqlalchemy import text
db = SessionLocal()
result = db.execute(text('SELECT name FROM sqlite_master WHERE type=\"table\" AND name=\"family_invitation_codes\"'))
print('Table exists:', result.fetchone() is not None)
db.close()
"
```

Expected output: `Table exists: True`

- [ ] **Step 5: Commit migration**

```bash
cd backend
git add alembic/versions/*add_family_invitation_code*.py
git commit -m "feat(db): add family_invitation_codes table migration

- Creates family_invitation_codes table
- Index on code column for fast lookup
- Foreign key to families table

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Write Backend Unit Tests

**Files:**
- Create: `backend/tests/test_family_invitation_code.py`

- [ ] **Step 1: Write test for valid invitation code**

Create `backend/tests/test_family_invitation_code.py`:

```python
"""Unit tests for family invitation code validation."""

import pytest
from app.errors import ErrorCode
from app.models.family_invitation_code import FamilyInvitationCode
from app.schemas.auth import RegisterRequest
from app.services import auth as auth_service


def test_register_with_valid_invitation_code(db):
    """Registration succeeds with valid unused invitation code."""
    # Create invitation code
    code = FamilyInvitationCode(code="TEST01")
    db.add(code)
    db.commit()

    # Register with code
    req = RegisterRequest(
        username="testuser",
        password="TestPass123",
        display_name="Test User",
        family_name="Test Family",
        family_invitation_code="TEST01"
    )
    tokens = auth_service.register(db, req, "127.0.0.1")

    assert tokens.access_token
    assert tokens.refresh_token

    # Verify code is marked as used
    used_code = db.query(FamilyInvitationCode).filter_by(code="TEST01").first()
    assert used_code.is_used is True
    assert used_code.used_by_username == "testuser"


def test_register_with_invalid_invitation_code(db):
    """Registration fails with non-existent invitation code."""
    req = RegisterRequest(
        username="testuser",
        password="TestPass123",
        display_name="Test User",
        family_name="Test Family",
        family_invitation_code="INVALID"
    )

    with pytest.raises(auth_service.AppError) as exc:
        auth_service.register(db, req, "127.0.0.1")

    assert exc.value.code == ErrorCode.FAMILY_INVITATION_CODE_NOT_FOUND


def test_register_with_already_used_code(db):
    """Registration fails with already-used invitation code."""
    # Create and use code
    code = FamilyInvitationCode(code="USED01", is_used=True)
    db.add(code)
    db.commit()

    req = RegisterRequest(
        username="testuser",
        password="TestPass123",
        display_name="Test User",
        family_name="Test Family",
        family_invitation_code="USED01"
    )

    with pytest.raises(auth_service.AppError) as exc:
        auth_service.register(db, req, "127.0.0.1")

    assert exc.value.code == ErrorCode.FAMILY_INVITATION_CODE_ALREADY_USED


def test_register_with_revoked_code(db):
    """Registration fails with revoked invitation code."""
    from datetime import datetime

    # Create revoked code
    code = FamilyInvitationCode(
        code="REVOKED",
        revoked_at=datetime.utcnow()
    )
    db.add(code)
    db.commit()

    req = RegisterRequest(
        username="testuser",
        password="TestPass123",
        display_name="Test User",
        family_name="Test Family",
        family_invitation_code="REVOKED"
    )

    with pytest.raises(auth_service.AppError) as exc:
        auth_service.register(db, req, "127.0.0.1")

    assert exc.value.code == ErrorCode.FAMILY_INVITATION_CODE_REVOKED


def test_invitation_code_normalized_to_uppercase(db):
    """Invitation code is normalized to uppercase on validation."""
    code = FamilyInvitationCode(code="ABC123")
    db.add(code)
    db.commit()

    req = RegisterRequest(
        username="testuser",
        password="TestPass123",
        display_name="Test User",
        family_name="Test Family",
        family_invitation_code="abc123"  # lowercase input
    )
    tokens = auth_service.register(db, req, "127.0.0.1")

    # Verify code was matched (normalized to uppercase)
    used_code = db.query(FamilyInvitationCode).filter_by(code="ABC123").first()
    assert used_code.is_used is True
```

- [ ] **Step 2: Run tests to verify they fail (TDD red phase)**

```bash
cd backend
uv run pytest tests/test_family_invitation_code.py -v
```

Expected: All tests PASS (service is already implemented from Task 4).

Note: If tests fail with import errors, check that all imports are correct.

- [ ] **Step 3: Run all backend tests to ensure no regressions**

```bash
cd backend
uv run pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 4: Commit tests**

```bash
cd backend
git add tests/test_family_invitation_code.py
git commit -m "test(auth): add family invitation code validation tests

- Test valid code registration
- Test invalid/non-existent code
- Test already-used code
- Test revoked code
- Test uppercase normalization

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 7: Create Admin CLI Script

**Files:**
- Create: `backend/scripts/family_invitation_codes.py`

- [ ] **Step 1: Write the CLI script**

Create `backend/scripts/family_invitation_codes.py`:

```python
"""Family invitation code management CLI.

Commands:
  generate --count N        Generate N unique invitation codes
  list [--format csv]       List all codes (table or CSV format)
  revoke --codes A,B,C      Revoke unused codes (comma-separated)
  link-existing             Retroactively link existing families

Usage examples:
  python scripts/family_invitation_codes.py generate --count 50
  python scripts/family_invitation_codes.py list --format csv --output launch_codes.csv
  python scripts/family_invitation_codes.py revoke --codes ABC123,DEF456
  python scripts/family_invitation_codes.py link-existing
"""

import argparse
import csv
import random
import string
import sys
from datetime import datetime, UTC
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.family import Family
from app.models.family_invitation_code import FamilyInvitationCode
from app.models.user import User


def generate_code() -> str:
    """Generate 6-character alphanumeric code (uppercase + digits)."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


def cmd_generate(count: int) -> None:
    """Generate N unique invitation codes.

    Ensures code uniqueness by checking existing codes.
    """
    db: Session = SessionLocal()
    try:
        codes: list[str] = []
        for _ in range(count):
            # Ensure uniqueness
            while True:
                code = generate_code()
                existing = db.query(FamilyInvitationCode).filter_by(code=code).first()
                if not existing:
                    break

            invitation = FamilyInvitationCode(code=code)
            db.add(invitation)
            codes.append(code)

        db.commit()
        print(f"Generated {count} invitation codes:")
        for code in codes:
            print(f"  {code}")
    except Exception as e:
        db.rollback()
        print(f"Error generating codes: {e}")
    finally:
        db.close()


def cmd_list(format: str, output: str | None) -> None:
    """List all invitation codes.

    Formats:
      table: Human-readable table (default)
      csv:   Export to CSV file or stdout
    """
    db: Session = SessionLocal()
    try:
        codes = db.query(FamilyInvitationCode).order_by(FamilyInvitationCode.created_at).all()

        if format == 'csv':
            rows = [
                ['code', 'is_used', 'used_by_family_id', 'used_by_username', 'revoked_at', 'created_at']
            ]
            for c in codes:
                rows.append([
                    c.code,
                    str(c.is_used),
                    c.used_by_family_id or '',
                    c.used_by_username or '',
                    c.revoked_at.isoformat() if c.revoked_at else '',
                    c.created_at.isoformat()
                ])

            if output:
                with open(output, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerows(rows)
                print(f"Exported {len(codes)} codes to {output}")
            else:
                for row in rows:
                    print(','.join(row))
        else:
            # Table format
            print(f"{'Code':<8} {'Used':<6} {'Family ID':<36} {'Username':<20} {'Status':<10}")
            print("-" * 80)
            for c in codes:
                status = 'revoked' if c.revoked_at else ('used' if c.is_used else 'available')
                family_id = c.used_by_family_id or '-'
                username = c.used_by_username or '-'
                print(f"{c.code:<8} {str(c.is_used):<6} {family_id:<36} {username:<20} {status:<10}")

            print(f"\nTotal: {len(codes)} codes")
    finally:
        db.close()


def cmd_revoke(codes_str: str) -> None:
    """Revoke unused invitation codes.

    Codes must be unused to be revoked.
    Comma-separated list for batch operations.
    """
    db: Session = SessionLocal()
    try:
        code_list = [c.strip().upper() for c in codes_str.split(',')]
        count = 0

        for code in code_list:
            record = db.query(FamilyInvitationCode).filter_by(code=code).first()

            if not record:
                print(f"Warning: Code '{code}' not found")
                continue

            if record.is_used:
                print(f"Warning: Code '{code}' already used, cannot revoke")
                continue

            if record.revoked_at:
                print(f"Warning: Code '{code}' already revoked")
                continue

            record.revoked_at = datetime.now(UTC).replace(tzinfo=None)
            count += 1

        db.commit()
        print(f"Revoked {count} codes successfully")
    except Exception as e:
        db.rollback()
        print(f"Error revoking codes: {e}")
    finally:
        db.close()


def cmd_link_existing() -> None:
    """Retroactively link existing families with invitation codes.

    For each existing family:
    1. Generate unique invitation code
    2. Create FamilyInvitationCode record
    3. Mark as used with family's metadata

    This preserves audit trail for families created before the feature launch.
    """
    db: Session = SessionLocal()
    try:
        families = db.query(Family).all()
        linked_count = 0

        print(f"Processing {len(families)} existing families...")

        for family in families:
            # Check if already linked
            existing = db.query(FamilyInvitationCode).filter_by(
                used_by_family_id=family.id
            ).first()
            if existing:
                print(f"  Family '{family.name}' already linked (code: {existing.code})")
                continue

            # Find the owner (created_by user)
            owner = db.query(User).filter_by(id=family.created_by).first()
            if not owner:
                print(f"  Warning: Family '{family.name}' has no owner (created_by={family.created_by})")
                continue

            # Generate unique code
            while True:
                code = generate_code()
                existing_code = db.query(FamilyInvitationCode).filter_by(code=code).first()
                if not existing_code:
                    break

            # Create retroactive record
            invitation = FamilyInvitationCode(
                code=code,
                is_used=True,
                used_at=family.created_at,
                used_by_family_id=family.id,
                used_by_username=owner.username
            )
            db.add(invitation)
            linked_count += 1
            print(f"  Family '{family.name}' -> code: {code} (owner: {owner.username})")

        db.commit()
        print(f"\nSuccessfully linked {linked_count} families with retroactive codes")
    except Exception as e:
        db.rollback()
        print(f"Error linking families: {e}")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Family invitation code management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    # generate command
    gen_parser = subparsers.add_parser('generate', help='Generate invitation codes')
    gen_parser.add_argument(
        '--count',
        type=int,
        default=10,
        help='Number of codes to generate (default: 10)'
    )

    # list command
    list_parser = subparsers.add_parser('list', help='List all invitation codes')
    list_parser.add_argument(
        '--format',
        choices=['table', 'csv'],
        default='table',
        help='Output format (default: table)'
    )
    list_parser.add_argument(
        '--output',
        type=str,
        help='Output file path for CSV format'
    )

    # revoke command
    revoke_parser = subparsers.add_parser('revoke', help='Revoke unused invitation codes')
    revoke_parser.add_argument(
        '--codes',
        type=str,
        required=True,
        help='Codes to revoke (comma-separated)'
    )

    # link-existing command
    link_parser = subparsers.add_parser(
        'link-existing',
        help='Retroactively link existing families'
    )

    args = parser.parse_args()

    if args.command == 'generate':
        cmd_generate(args.count)
    elif args.command == 'list':
        cmd_list(args.format, args.output)
    elif args.command == 'revoke':
        cmd_revoke(args.codes)
    elif args.command == 'link-existing':
        cmd_link_existing()


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Test generate command**

```bash
cd backend
python scripts/family_invitation_codes.py generate --count 5
```

Expected output:
```
Generated 5 invitation codes:
  ABC123
  DEF456
  ...
```

- [ ] **Step 3: Test list command**

```bash
cd backend
python scripts/family_invitation_codes.py list
```

Expected output: Table with generated codes showing status 'available'.

- [ ] **Step 4: Test revoke command**

```bash
cd backend
# First get a code from the list output
python scripts/family_invitation_codes.py revoke --codes ABC123
```

Expected output: `Revoked 1 codes successfully`

- [ ] **Step 5: Commit script**

```bash
cd backend
git add scripts/family_invitation_codes.py
git commit -m "feat(scripts): add family invitation code management CLI

Commands:
- generate --count N: batch create codes
- list [--format csv]: view/export codes
- revoke --codes A,B,C: revoke unused codes
- link-existing: retroactive linking

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 8: Update Frontend Types

**Files:**
- Modify: `frontend/src/types/index.ts:215-220`

- [ ] **Step 1: Add family_invitation_code to RegisterRequest**

Modify `frontend/src/types/index.ts` lines 215-220:

```typescript
export interface RegisterRequest {
  family_invitation_code: string  // NEW: required for family creation
  family_name: string
  username: string
  display_name: string
  password: string
  altcha?: string
}
```

- [ ] **Step 2: Run TypeScript type check**

```bash
cd frontend
npm run typecheck
```

Expected: Type errors about missing field in RegisterPage.vue (this is expected, will be fixed in Task 9).

- [ ] **Step 3: Commit type changes**

```bash
cd frontend
git add src/types/index.ts
git commit -m "feat(types): add family_invitation_code to RegisterRequest

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 9: Update RegisterPage.vue

**Files:**
- Modify: `frontend/src/pages/RegisterPage.vue:108-114, 130-157`

- [ ] **Step 1: Add invitation code to form state**

Modify `frontend/src/pages/RegisterPage.vue` lines 108-114:

```typescript
const form = ref({
  family_invitation_code: '',  // NEW
  family_name: '',
  username: '',
  display_name: '',
  password: '',
  altcha: undefined as string | undefined
})
```

- [ ] **Step 2: Add invitation code input field (FIRST field)**

Modify `frontend/src/pages/RegisterPage.vue` template, add before family_name field (around line 10):

```vue
      <van-cell-group inset>
        <!-- NEW: Family invitation code field (FIRST) -->
        <van-field
          v-model="form.family_invitation_code"
          label="家庭邀请码"
          placeholder="请输入6位邀请码"
          maxlength="6"
          :formatter="formatInvitationCode"
          format-trigger="onBlur"
          :rules="[{ required: true, message: '请输入家庭邀请码' }]"
          :error-message="getError('family_invitation_code')?.msg"
          @blur="validateField('family_invitation_code')"
        />

        <van-field
          v-model="form.family_name"
          label="家庭名称"
          placeholder="请输入家庭名称"
          :rules="[{ required: true, message: '请输入家庭名称' }]"
          :error-message="getError('family_name')?.msg"
          @blur="validateField('family_name')"
        />
        <!-- ... rest of existing fields ... -->
```

- [ ] **Step 3: Add formatInvitationCode function**

Add to `<script setup>` section (after form definition):

```typescript
// NEW: Formatter for invitation code (uppercase on blur)
function formatInvitationCode(value: string): string {
  return value.toUpperCase()
}
```

- [ ] **Step 4: Update error handling in onSubmit**

Modify `frontend/src/pages/RegisterPage.vue` onSubmit function error handling (around line 140):

```typescript
  } catch (error: any) {
    // Handle field-level validation errors (422)
    setErrors(error)

    // Handle specific error codes
    const code = error.response?.data?.code || ''
    const message = error.response?.data?.message || ''
    const status = error.response?.status

    // NEW: Handle invitation code specific errors
    if (code === 'FAMILY_INVITATION_CODE_NOT_FOUND') {
      showToast(message || '邀请码不存在')
    } else if (code === 'FAMILY_INVITATION_CODE_ALREADY_USED') {
      showToast(message || '邀请码已被使用')
    } else if (code === 'FAMILY_INVITATION_CODE_REVOKED') {
      showToast(message || '邀请码已被撤销')
    } else if (status === 503 || code === 'CAPTCHA_SERVICE_UNAVAILABLE') {
      showToast(message || '验证服务暂时不可用，请稍后重试')
    } else if (code.startsWith('CAPTCHA_')) {
      altchaRef.value?.reset()
      showToast(message)
    }
  } finally {
```

- [ ] **Step 5: Run TypeScript type check**

```bash
cd frontend
npm run typecheck
```

Expected: PASS (no type errors).

- [ ] **Step 6: Run build**

```bash
cd frontend
npm run build
```

Expected: Build succeeds.

- [ ] **Step 7: Commit frontend changes**

```bash
cd frontend
git add src/pages/RegisterPage.vue
git commit -m "feat(register): add family invitation code input field

- Required field (first in form)
- Auto-uppercase formatting
- 6-character limit
- Specific error handling for invalid/used/revoked codes

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 10: Integration Verification

- [ ] **Step 1: Start backend server**

```bash
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

Run in background or separate terminal.

- [ ] **Step 2: Generate test invitation code**

```bash
cd backend
python scripts/family_invitation_codes.py generate --count 1
```

Note the generated code (e.g., "ABC123").

- [ ] **Step 3: Start frontend dev server**

```bash
cd frontend
npm run dev
```

Run in background or separate terminal.

- [ ] **Step 4: Open browser and navigate to register page**

Open `http://localhost:5173/register` (or appropriate URL).

- [ ] **Step 5: Verify UI shows invitation code field**

Check:
- Invitation code field is visible
- It's the first field in the form
- Label is "家庭邀请码"
- Placeholder is "请输入6位邀请码"

- [ ] **Step 6: Test registration with valid code**

Fill form:
- Invitation code: ABC123 (from Step 2)
- Family name: Test Family
- Username: testuser123
- Display name: Test User
- Password: TestPass123

Submit and verify:
- Registration succeeds
- Redirects to dashboard

- [ ] **Step 7: Test registration with invalid code**

Navigate back to register. Fill form with:
- Invitation code: INVALID
- Other valid fields

Submit and verify:
- Toast shows "邀请码不存在"

- [ ] **Step 8: Test already-used code**

Navigate back to register. Fill form with:
- Invitation code: ABC123 (same as Step 6)
- Other valid fields

Submit and verify:
- Toast shows "邀请码已被使用"

- [ ] **Step 9: Verify code marked as used in script**

```bash
cd backend
python scripts/family_invitation_codes.py list
```

Expected: ABC123 shows `is_used=True` with username "testuser123".

- [ ] **Step 10: Kill servers**

Stop backend and frontend servers.

---

## Task 11: Retroactive Linking (Pre-deployment)

- [ ] **Step 1: Run link-existing script**

```bash
cd backend
python scripts/family_invitation_codes.py link-existing
```

Expected output:
```
Processing N existing families...
  Family '...' -> code: XXXXXX (owner: ...)
Successfully linked N families with retroactive codes
```

- [ ] **Step 2: Verify retroactive codes in database**

```bash
cd backend
python scripts/family_invitation_codes.py list
```

Expected: All existing families have codes marked as used.

- [ ] **Step 3: Commit retroactive linking**

Document the linking in a note (this is a one-time operation, not code change):
```bash
cd backend
# Create a log file documenting the operation
echo "$(date): Retroactive linking completed for existing families" >> scripts/link_existing.log
git add scripts/link_existing.log
git commit -m "chore: document retroactive family invitation code linking

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 12: Final Documentation Update

**Files:**
- Modify: `CLAUDE.md` (root)

- [ ] **Step 1: Add invitation code section to CLAUDE.md**

Add to `CLAUDE.md` after the "Authentication" section:

```markdown
### Family Invitation Code (Launch Control)

- **Purpose**: Control family creation during initial launch
- **Table**: `family_invitation_codes` (single-use 6-char codes)
- **Admin script**: `backend/scripts/family_invitation_codes.py`
  - `generate --count N` — batch create codes
  - `list [--format csv]` — view/export codes
  - `revoke --codes A,B,C` — revoke unused codes
  - `link-existing` — retroactive linking for existing families
- **Registration**: Requires valid unused code
- **Error codes**: `FAMILY_INVITATION_CODE_NOT_FOUND`, `ALREADY_USED`, `REVOKED`
```

- [ ] **Step 2: Commit documentation**

```bash
git add CLAUDE.md
git commit -m "docs: document family invitation code feature in CLAUDE.md

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Summary

**Implementation order:**
1. Model + error codes (backend infrastructure)
2. Schema + service (backend validation)
3. Migration (database)
4. Tests (verification)
5. Admin script (management tool)
6. Frontend types + UI (user interface)
7. Integration test (end-to-end)
8. Retroactive linking (migration helper)
9. Documentation

**Deployment order (CRITICAL):**
1. Run migration (`alembic upgrade head`)
2. Run retroactive linking (`python scripts/family_invitation_codes.py link-existing`)
3. Deploy backend code
4. Deploy frontend code
5. Generate launch codes (`python scripts/family_invitation_codes.py generate --count 50`)

**Testing coverage:**
- Backend: 5 unit tests for validation scenarios
- Frontend: Type check + build verification
- Integration: Manual registration flow test

**Files created/modified:**
- Created: 4 files (model, migration, tests, script)
- Modified: 6 files (codes, schema, service, alembic env, types, RegisterPage, CLAUDE.md)

**Total commits:** ~12 commits following TDD workflow