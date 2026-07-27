"""场景: test_empty — 空家庭，仅有账号，无任何资产/负债/心愿。"""

from sqlalchemy.orm import Session

from factories.users import FamilyFactory, UserFactory, next_id


def seed_empty_scenario(db: Session, verbose: bool = False) -> None:
    user, created = UserFactory.get_or_create(
        db,
        username="test_empty",
        display_name="空家庭测试",
        password="TestEmpty123!",
        family_id=0,  # placeholder, replaced below
        role="owner",
        avatar_color="#6366F1",
        flush=False,
    )

    if not created:
        if verbose:
            print("  [skip] test_empty 已存在")
        return

    # Create family with the real user id
    fam = FamilyFactory.get_or_create(db, name="空家庭", created_by_id=user.id)
    user.family_id = fam.id
    db.flush()

    print("  [ok] test_empty — 空家庭账号已创建")
