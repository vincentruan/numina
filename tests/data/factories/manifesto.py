"""家庭约定工厂 — 幂等创建，按 family_id 查重。"""

from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Session

from models import FamilyManifesto, ManifestoSignature, ManifestoVersion
from factories.users import next_id


class ManifestoFactory:
    @staticmethod
    def get_or_create(
        db: Session,
        *,
        family_id: int,
        created_by: int,
        title: str = "家庭约定",
        body: str = "我们约定：互相尊重、共同成长。",
        template_id: str = "default",
        signing_deadline: Optional[str] = None,
    ) -> tuple[FamilyManifesto, bool]:
        existing = (
            db.query(FamilyManifesto)
            .filter(FamilyManifesto.family_id == family_id, FamilyManifesto.status == "active")
            .first()
        )
        if existing:
            return existing, False

        manifesto = FamilyManifesto(
            id=next_id(),
            family_id=family_id,
            status="active",
            signing_deadline=signing_deadline,
            created_by=created_by,
        )
        db.add(manifesto)
        db.flush()

        version = ManifestoVersion(
            id=next_id(),
            manifesto_id=manifesto.id,
            version_number=1,
            template_id=template_id,
            title=title,
            body=body,
            change_type="initial",
            created_by=created_by,
        )
        db.add(version)
        db.flush()

        manifesto.current_version_id = version.id
        db.flush()
        return manifesto, True

    @staticmethod
    def sign(
        db: Session,
        *,
        version_id: int,
        user_id: int,
        signature_data: str | None = None,
    ) -> tuple[ManifestoSignature, bool]:
        existing = (
            db.query(ManifestoSignature)
            .filter(ManifestoSignature.version_id == version_id, ManifestoSignature.user_id == user_id)
            .first()
        )
        if existing:
            return existing, False

        sig = ManifestoSignature(
            id=next_id(),
            version_id=version_id,
            user_id=user_id,
            signature_data=signature_data,
        )
        db.add(sig)
        db.flush()
        return sig, True
