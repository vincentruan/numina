---
title: Family Invitation Code Feature Design
created: 2026-04-22
status: approved
author: Claude + User
purpose: Control family creation during initial launch via invitation code requirement
---

# Family Invitation Code Feature Design

## Overview

Numina is a privacy-first, self-hosted family asset visualization system. During initial launch, we need to control who can create new families to prevent unauthorized usage. This design introduces a **family invitation code** system that gates family creation while preserving complete audit trail and enabling easy admin management.

**Key Decisions (validated via brainstorming):**
- Single-use codes (each code creates one family)
- 6-character alphanumeric format (uppercase + digits)
- Full tracking: family_id, used_at, used_by_username
- Specific error messages for invalid/used/revoked codes
- Retroactive linking for existing families
- Batch script management (generate, list, revoke, export)

---

## Data Model

### FamilyInvitationCode Table

```python
# backend/app/models/family_invitation_code.py

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

**Field Rationale:**

| Field | Purpose | Notes |
|-------|---------|-------|
| `id` | Primary key | UUID for consistency with other tables |
| `code` | 6-char invitation code | Uppercase letters + digits, unique constraint |
| `is_used` | Usage flag | Boolean for quick filtering |
| `used_at` | Timestamp | When code was consumed |
| `used_by_family_id` | Family link | FK to families.id for audit and future queries |
| `used_by_username` | User tracking | Which username used this code |
| `revoked_at` | Revocation timestamp | NULL = not revoked, non-NULL = revoked by admin |
| `created_at` | Creation timestamp | For audit and age-based cleanup |

---

## Backend API Changes

### Schema Updates

```python
# backend/app/schemas/auth.py

class RegisterRequest(BaseModel):
    """Registration request with family invitation code requirement."""

    username: str
    password: str
    display_name: str
    family_name: str
    family_invitation_code: str  # NEW: required for family creation
    altcha: str | None = None  # Captcha payload

    @field_validator("family_invitation_code")
    @classmethod
    def normalize_invitation_code(cls, v: str) -> str:
        """Normalize to uppercase for consistent matching."""
        return v.upper().strip()

    @field_validator("username")
    @classmethod
    def check_username(cls, v: str) -> str:
        return validate_username(v)

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return validate_password_strength(v)
```

### New Error Codes

```python
# backend/app/errors/codes.py

class ErrorCode(Enum):
    # Authentication errors (existing)
    AUTH_USERNAME_EXISTS = "AUTH_USERNAME_EXISTS"
    AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
    AUTH_INVITE_CODE_INVALID = "AUTH_INVITE_CODE_INVALID"
    AUTH_RATE_LIMITED = "AUTH_RATE_LIMITED"
    # ... other existing codes ...

    # Family invitation code errors (NEW)
    FAMILY_INVITATION_CODE_NOT_FOUND = "FAMILY_INVITATION_CODE_NOT_FOUND"
    FAMILY_INVITATION_CODE_ALREADY_USED = "FAMILY_INVITATION_CODE_ALREADY_USED"
    FAMILY_INVITATION_CODE_REVOKED = "FAMILY_INVITATION_CODE_REVOKED"
```

**Error Messages (Chinese):**

| Code | Message | HTTP Status |
|------|---------|-------------|
| `FAMILY_INVITATION_CODE_NOT_FOUND` | "邀请码不存在" | 400 |
| `FAMILY_INVITATION_CODE_ALREADY_USED` | "邀请码已被使用" | 400 |
| `FAMILY_INVITATION_CODE_REVOKED` | "邀请码已被撤销" | 400 |

### Service Layer Changes

```python
# backend/app/services/auth.py

from app.models.family_invitation_code import FamilyInvitationCode
from app.errors import AppError, ErrorCode


def register(
    db: Session, req: RegisterRequest, client_ip: str = "unknown"
) -> TokenResponse:
    """Register a new user with invitation code validation.

    Steps:
    1. Check registration rate limit
    2. Validate family invitation code
    3. Check username uniqueness
    4. Create family and user
    5. Mark invitation code as used
    6. Return JWT tokens
    """
    # 1. Check registration rate limit (existing)
    _check_register_rate_limit(client_ip)

    # 2. Validate family invitation code (NEW)
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

    # 3. Check username exists (existing)
    if db.query(User).filter(User.username == req.username).first():
        raise AppError(ErrorCode.AUTH_USERNAME_EXISTS)

    # 4. Create family and user (existing, unchanged)
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

    # 5. Mark invitation code as used (NEW)
    invitation_code.is_used = True
    invitation_code.used_at = datetime.utcnow()
    invitation_code.used_by_family_id = family_id
    invitation_code.used_by_username = req.username

    db.commit()

    # 6. Record successful registration and log (existing)
    _record_register_attempt(client_ip)
    _log_security_event(
        SecurityEventType.REGISTER_SUCCESS,
        username=req.username,
        user_id=user_id,
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

---

## Frontend Changes

### Type Updates

```typescript
// frontend/src/types/index.ts

export interface RegisterRequest {
  username: string
  password: string
  display_name: string
  family_name: string
  family_invitation_code: string  // NEW: required field
  altcha?: string
}
```

### RegisterPage.vue Changes

```vue
<!-- frontend/src/pages/RegisterPage.vue -->

<template>
  <div class="register-page">
    <div class="register-header">
      <h1 class="app-title">创建家庭</h1>
      <p class="app-subtitle">创建一个新的家庭账本</p>
    </div>

    <van-form class="register-form" @submit="onSubmit">
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

        <!-- Existing fields -->
        <van-field
          v-model="form.family_name"
          label="家庭名称"
          placeholder="请输入家庭名称"
          :rules="[{ required: true, message: '请输入家庭名称' }]"
          :error-message="getError('family_name')?.msg"
          @blur="validateField('family_name')"
        />
        <van-field
          v-model="form.username"
          label="用户名"
          placeholder="请输入用户名"
          :rules="[{ required: true, message: '请输入用户名' }]"
          :error-message="getError('username')?.msg"
          @blur="validateField('username')"
        />
        <van-field
          v-model="form.display_name"
          label="显示名称"
          placeholder="请输入显示名称"
          :rules="[{ required: true, message: '请输入显示名称' }]"
          @blur="validateField('display_name')"
        />

        <!-- Password fields (unchanged) -->
        <div class="password-field-wrapper">
          <van-field
            v-model="form.password"
            :type="showPassword ? 'text' : 'password'"
            label="密码"
            placeholder="请输入密码(至少6位)"
            :rules="[
              { required: true, message: '请输入密码' },
              { validator: validatePassword, message: '密码至少6位' }
            ]"
            :error-message="getError('password')?.msg"
            @blur="validateField('password')"
          >
            <template #right-icon>
              <van-icon
                :name="showPassword ? 'eye-o' : 'closed-eye'"
                @click="showPassword = !showPassword"
              />
            </template>
          </van-field>
          <PasswordStrengthIndicator :password="form.password" />
        </div>

        <div class="password-field-wrapper">
          <van-field
            v-model="confirmPassword"
            :type="showConfirmPassword ? 'text' : 'password'"
            label="确认密码"
            placeholder="请再次输入密码"
            :rules="[
              { required: true, message: '请确认密码' },
              { validator: validateConfirmPassword, message: '两次密码不一致' }
            ]"
            @blur="validateField('confirm')"
          >
            <template #right-icon>
              <van-icon
                :name="showConfirmPassword ? 'eye-o' : 'closed-eye'"
                @click="showConfirmPassword = !showConfirmPassword"
              />
            </template>
          </van-field>
        </div>
      </van-cell-group>

      <!-- ALTCHA captcha widget -->
      <AltchaWidget ref="altchaRef" v-model="form.altcha" endpoint="register" />

      <div class="form-actions">
        <van-button
          round
          block
          type="primary"
          native-type="submit"
          :loading="loading"
        >
          创建并注册
        </van-button>
      </div>
    </van-form>

    <div class="register-links">
      <router-link to="/login">已有账号？去登录</router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, provide } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { useAuthStore } from '@/stores/auth'
import AltchaWidget from '@/components/common/AltchaWidget.vue'
import PasswordStrengthIndicator from '@/components/common/PasswordStrengthIndicator.vue'
import { useValidationErrors, validationErrorsKey } from '@/composables/useValidationErrors'

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const confirmPassword = ref('')
const altchaRef = ref()
const showPassword = ref(false)
const showConfirmPassword = ref(false)

const validationErrorsComposable = useValidationErrors()
const { setErrors, clearErrors, getError } = validationErrorsComposable
provide(validationErrorsKey, validationErrorsComposable)

const form = ref({
  family_invitation_code: '',  // NEW
  family_name: '',
  username: '',
  display_name: '',
  password: '',
  altcha: undefined as string | undefined
})

// NEW: Formatter for invitation code (uppercase on blur)
function formatInvitationCode(value: string): string {
  return value.toUpperCase()
}

// Existing validation functions (unchanged)
function validatePassword(value: string): boolean {
  return value.length >= 6
}

function validateConfirmPassword(value: string): boolean {
  return value === form.value.password
}

function validateField(field: string) {
  // Vant's van-field handles this via :rules prop
}

async function onSubmit() {
  clearErrors()
  loading.value = true
  try {
    await authStore.register(form.value)
    showToast('注册成功')
    router.push('/')
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
    loading.value = false
  }
}
</script>
```

### UI/UX Considerations

1. **Field order**: Invitation code appears first to gate the entire registration flow
2. **Input formatting**: Auto-uppercase on blur for consistent matching
3. **Input validation**: 6-character limit via `maxlength="6"`
4. **Error display**: Field-level error via Vant's `error-message` + toast for specific error codes

---

## Admin Script Design

### Script Location

```
backend/scripts/
└── family_invitation_codes.py  # NEW: CLI tool for admin operations
```

### CLI Commands

```bash
# Generate N codes
python scripts/family_invitation_codes.py generate --count 10

# List all codes (table format)
python scripts/family_invitation_codes.py list

# Export to CSV
python scripts/family_invitation_codes.py list --format csv --output codes.csv

# Revoke unused codes
python scripts/family_invitation_codes.py revoke --codes A1B2C3,D4E5F6

# Retroactive linking for existing families
python scripts/family_invitation_codes.py link-existing
```

### Implementation

```python
# backend/scripts/family_invitation_codes.py

"""
Family invitation code management CLI.

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

### Batch Operations Summary

| Command | Purpose | Output |
|---------|---------|--------|
| `generate --count N` | Create N unique codes | Prints list of generated codes |
| `list` | View all codes | Human-readable table with status |
| `list --format csv --output file.csv` | Export to CSV | CSV with 6 columns (code, used, family_id, username, revoked_at, created_at) |
| `revoke --codes A,B,C` | Bulk revoke unused codes | Success count + warnings for invalid codes |
| `link-existing` | Retroactive migration | Linked family count with details |

---

## Migration Strategy

### Deployment Order (CRITICAL)

**MUST follow this exact order:**

1. **Database migration FIRST** — Create table before backend code deployment
2. **Retroactive linking SECOND** — Link existing families before new registrations
3. **Backend deployment THIRD** — New validation logic
4. **Frontend deployment FOURTH** — Updated registration form

If backend is deployed before migration, model import will fail.

---

### Phase 1: Database Migration

```bash
# Create Alembic migration
cd backend
uv run alembic revision --autogenerate -m "add_family_invitation_code_table"

# Apply migration
uv run alembic upgrade head
```

**Migration file:**

```python
# backend/alembic/versions/xxx_add_family_invitation_code_table.py

def upgrade():
    op.create_table(
        'family_invitation_codes',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('code', sa.String(6), unique=True, nullable=False),
        sa.Column('is_used', sa.Boolean(), default=False, nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('used_by_family_id', sa.String(36), sa.ForeignKey('families.id'), nullable=True),
        sa.Column('used_by_username', sa.String(50), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        'ix_family_invitation_codes_code',
        'family_invitation_codes',
        ['code']
    )


def downgrade():
    op.drop_index('ix_family_invitation_codes_code')
    op.drop_table('family_invitation_codes')
```

---

### Phase 2: Retroactive Linking

```bash
# Link existing families with invitation codes
cd backend
python scripts/family_invitation_codes.py link-existing
```

**Expected output:**

```
Processing 5 existing families...
  Family '张氏家庭' -> code: X1Y2Z3 (owner: zhangsan)
  Family '李氏家庭' -> code: A4B5C6 (owner: lisi)
  Family '王家' -> code: D7E8F9 (owner: wangwu)
  Family '测试家庭' -> code: G0H1I2 (owner: testuser)
  Family '开发家庭' -> code: J3K4L5 (owner: devuser)

Successfully linked 5 families with retroactive codes
```

---

### Phase 3: Backend Deployment

Deploy backend with:
- Updated `RegisterRequest` schema
- Updated `register()` service with validation logic
- New error codes in `ErrorCode` enum
- Updated error messages in Chinese

---

### Phase 4: Frontend Deployment

Deploy frontend with:
- Updated `RegisterPage.vue` with invitation code field
- Updated `RegisterRequest` type
- Enhanced error handling for new error codes

---

### Phase 5: Launch Day Operations

```bash
# Generate initial batch of codes for distribution
cd backend
python scripts/family_invitation_codes.py generate --count 50

# Output for distribution (email, Slack, etc.):
# Generated 50 invitation codes:
#   Q1W2E3, R4T5Y6, U7I8O9, P0A1S2, D3F4G5, ...

# Monitor usage during launch
python scripts/family_invitation_codes.py list

# Revoke unused codes if needed
python scripts/family_invitation_codes.py revoke --codes Q1W2E3,R4T5Y6
```

---

## Rollback Plan

### Option A: Config-Based Emergency Bypass

```python
# backend/app/config.py

class Settings(BaseSettings):
    # ... existing settings ...

    # Emergency bypass for invitation code requirement
    REQUIRE_FAMILY_INVITATION_CODE: bool = True
```

```python
# backend/app/services/auth.py

def register(db: Session, req: RegisterRequest, client_ip: str) -> TokenResponse:
    if settings.REQUIRE_FAMILY_INVITATION_CODE:
        # Validate invitation code
        invitation_code = db.query(FamilyInvitationCode).filter_by(
            code=req.family_invitation_code
        ).first()
        # ... validation logic ...
    else:
        # Bypass validation (set REQUIRE_FAMILY_INVITATION_CODE=false)
        pass

    # Rest of registration logic unchanged
```

**Usage:** Set `REQUIRE_FAMILY_INVITATION_CODE=false` in `.env` to bypass without removing feature.

---

### Option B: Full Rollback

```bash
# 1. Revert backend code
cd backend
git revert <commit-hash>

# 2. Revert frontend code
cd frontend
git revert <commit-hash>

# 3. Drop table (if needed)
cd backend
uv run alembic downgrade -1

# Output:
# Running downgrade xxx_add_family_invitation_code_table...
# Dropping index ix_family_invitation_codes_code
# Dropping table family_invitation_codes
```

---

## Testing

### Backend Unit Tests

```python
# backend/tests/test_family_invitation_code.py

import pytest
from app.errors import ErrorCode
from app.models.family_invitation_code import FamilyInvitationCode
from app.schemas.auth import RegisterRequest
from app.services import auth as auth_service


def test_register_with_valid_invitation_code(db, client):
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

    with pytest.raises(AppError) as exc:
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

    with pytest.raises(AppError) as exc:
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

    with pytest.raises(AppError) as exc:
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

---

### Frontend Tests

```typescript
// frontend/src/pages/RegisterPage.test.ts

import { mount } from '@vue/test-utils'
import { describe, it, expect, vi } from 'vitest'
import RegisterPage from './RegisterPage.vue'

describe('RegisterPage', () => {
  it('shows invitation code field as first field', () => {
    const wrapper = mount(RegisterPage)
    const fields = wrapper.findAllComponents({ name: 'VanField' })

    expect(fields[0].props('label')).toBe('家庭邀请码')
  })

  it('requires invitation code input', () => {
    const wrapper = mount(RegisterPage)
    const invitationField = wrapper.findComponent({ name: 'VanField' })

    expect(invitationField.props('rules')).toContainEqual(
      { required: true, message: '请输入家庭邀请码' }
    )
  })

  it('limits invitation code to 6 characters', () => {
    const wrapper = mount(RegisterPage)
    const invitationField = wrapper.findComponent({ name: 'VanField' })

    expect(invitationField.props('maxlength')).toBe(6)
  })

  it('formats invitation code to uppercase', async () => {
    const wrapper = mount(RegisterPage)
    const form = wrapper.vm.form

    form.family_invitation_code = 'abc123'
    wrapper.vm.formatInvitationCode(form.family_invitation_code)

    expect(form.family_invitation_code).toBe('ABC123')
  })

  it('shows specific error for invalid invitation code', async () => {
    const wrapper = mount(RegisterPage)
    const mockError = {
      response: {
        data: {
          code: 'FAMILY_INVITATION_CODE_NOT_FOUND',
          message: '邀请码不存在'
        }
      }
    }

    await wrapper.vm.onSubmit()
    // Trigger error handling...

    expect(wrapper.vm.showToast).toHaveBeenCalledWith('邀请码不存在')
  })
})
```

---

## Security Considerations

### Code Generation Security

- **Randomness**: Uses Python's `random.choices()` for code generation (suitable for launch control, not cryptographic secrets)
- **Uniqueness guarantee**: Database query checks for existing codes before insertion
- **6-character length**: 36^6 = ~2 billion possible combinations (sufficient for launch control)

### Brute Force Protection

- **Rate limiting**: Existing registration rate limit (5 per hour per IP) protects against brute force
- **Invalid code attempts**: Logged via `_log_security_event()` for monitoring
- **No enumeration**: Specific error messages don't reveal which codes exist vs are used

### Audit Trail Integrity

- **Immutable records**: Used codes cannot be deleted or modified (only revoked unused codes)
- **Complete tracking**: family_id, username, timestamp for every used code
- **Retroactive linking**: Preserves audit trail for pre-existing families

---

## Future Extensions (Not in Current Scope)

The following features are documented for future consideration but NOT part of this implementation:

1. **Multi-use codes**: Allow codes to create N families (add `max_uses` and `current_uses` fields)
2. **Expiration dates**: Add `expires_at` field for time-limited codes
3. **Code labels/notes**: Add `label` field for categorization (e.g., "beta testers", "partners")
4. **Admin UI**: Web interface for code management (currently CLI-only per requirements)
5. **Email distribution**: Script integration with email service for automated code distribution
6. **Config toggle**: `REQUIRE_FAMILY_INVITATION_CODE` env flag for post-launch flexibility

---

## Summary

This design introduces a family invitation code system to control family creation during Numina's initial launch:

**Key Components:**
- Dedicated `FamilyInvitationCode` table with complete audit trail
- Backend validation in `register()` service with specific error messages
- Frontend field in `RegisterPage.vue` with uppercase formatting
- Admin CLI script for batch operations (generate, list, revoke, export)
- Retroactive linking for existing families via script

**Deployment:**
- Migration-first deployment order (critical)
- Script-based code management (no UI required)
- Rollback plan via config toggle or Alembic downgrade

**Testing:**
- Backend unit tests for all validation scenarios
- Frontend tests for field behavior and error handling

This design is complete and ready for implementation planning.