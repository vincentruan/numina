def test_create_blind_box_gift(db):
    from app.models.blind_box_gift import BlindBoxGift
    gift = BlindBoxGift(
        family_id=1,
        name="乐高积木",
        value_score=8,
        created_by=1,
    )
    db.add(gift)
    db.commit()
    assert gift.id is not None
    assert gift.is_active is True
