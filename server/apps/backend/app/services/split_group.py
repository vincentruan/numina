"""Split group service — manage split groups and participants for shared travel expenses."""

from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from packages.db.models.split_group import (
    SplitGroup,
    SplitParticipant,
    TripCoOrganizer,
    generate_invite_code,
)
from packages.db.models.trip import Trip

_MAX_PARTICIPANTS = 20
_MAX_CO_ORGANIZERS = 3


def _get_trip(db: Session, trip_id: int, family_id: int) -> Trip:
    """Validate trip exists and belongs to family."""
    trip = (
        db.query(Trip).filter(Trip.id == trip_id, Trip.family_id == family_id).first()
    )
    if not trip:
        raise AppError(ErrorCode.TRIP_NOT_FOUND)
    return trip


def create_group(db: Session, trip_id: int, family_id: int, user_id: int) -> SplitGroup:
    """Create a split group for a trip."""
    _get_trip(db, trip_id, family_id)

    existing = (
        db.query(SplitGroup)
        .filter(SplitGroup.trip_id == trip_id, SplitGroup.is_active == True)  # noqa: E712
        .first()
    )
    if existing:
        raise AppError(ErrorCode.SPLIT_GROUP_ALREADY_EXISTS)

    group = SplitGroup(
        trip_id=trip_id,
        invite_code=generate_invite_code(),
        created_by_user_id=user_id,
    )
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


def join_group(
    db: Session, invite_code: str, name: str
) -> tuple[SplitParticipant, SplitGroup]:
    """Join a split group via invite code. Returns (participant, group)."""
    group = (
        db.query(SplitGroup)
        .filter(SplitGroup.invite_code == invite_code, SplitGroup.is_active == True)  # noqa: E712
        .first()
    )
    if not group:
        raise AppError(ErrorCode.SPLIT_GROUP_NOT_FOUND)

    count = (
        db.query(SplitParticipant).filter(SplitParticipant.group_id == group.id).count()
    )
    if count >= _MAX_PARTICIPANTS:
        raise AppError(ErrorCode.SPLIT_PARTICIPANT_LIMIT)

    duplicate = (
        db.query(SplitParticipant)
        .filter(SplitParticipant.group_id == group.id, SplitParticipant.name == name)
        .first()
    )
    if duplicate:
        raise AppError(ErrorCode.SPLIT_PARTICIPANT_NAME_CONFLICT)

    participant = SplitParticipant(group_id=group.id, name=name)
    db.add(participant)
    db.commit()
    db.refresh(participant)
    return participant, group


def get_group(db: Session, trip_id: int, family_id: int) -> SplitGroup:
    """Get split group for a trip with participants."""
    _get_trip(db, trip_id, family_id)

    group = (
        db.query(SplitGroup)
        .filter(SplitGroup.trip_id == trip_id, SplitGroup.is_active == True)  # noqa: E712
        .first()
    )
    if not group:
        raise AppError(ErrorCode.SPLIT_GROUP_NOT_FOUND)
    return group


def get_group_with_participants(db: Session, trip_id: int, family_id: int) -> dict:
    """Get split group with participants list."""
    group = get_group(db, trip_id, family_id)
    participants = (
        db.query(SplitParticipant)
        .filter(SplitParticipant.group_id == group.id)
        .order_by(SplitParticipant.joined_at)
        .all()
    )
    return {"group": group, "participants": participants}


def add_participant(
    db: Session,
    group_id: int,
    name: str,
    family_id: int | None = None,
) -> SplitParticipant:
    """Add a participant to a group."""
    count = (
        db.query(SplitParticipant).filter(SplitParticipant.group_id == group_id).count()
    )
    if count >= _MAX_PARTICIPANTS:
        raise AppError(ErrorCode.SPLIT_PARTICIPANT_LIMIT)

    duplicate = (
        db.query(SplitParticipant)
        .filter(SplitParticipant.group_id == group_id, SplitParticipant.name == name)
        .first()
    )
    if duplicate:
        raise AppError(ErrorCode.SPLIT_PARTICIPANT_NAME_CONFLICT)

    participant = SplitParticipant(group_id=group_id, name=name, family_id=family_id)
    db.add(participant)
    db.commit()
    db.refresh(participant)
    return participant


def remove_participant(db: Session, participant_id: int, family_id: int) -> None:
    """Remove a participant from a group."""
    participant = (
        db.query(SplitParticipant).filter(SplitParticipant.id == participant_id).first()
    )
    if not participant:
        raise AppError(ErrorCode.SPLIT_PARTICIPANT_NOT_FOUND)

    # Validate the group's trip belongs to the family
    group = db.query(SplitGroup).filter(SplitGroup.id == participant.group_id).first()
    if group:
        _get_trip(db, group.trip_id, family_id)

    db.delete(participant)
    db.commit()


def regenerate_code(db: Session, group_id: int, family_id: int) -> SplitGroup:
    """Generate a new invite code for the group."""
    group = db.query(SplitGroup).filter(SplitGroup.id == group_id).first()
    if not group:
        raise AppError(ErrorCode.SPLIT_GROUP_NOT_FOUND)

    _get_trip(db, group.trip_id, family_id)

    group.invite_code = generate_invite_code()
    db.commit()
    db.refresh(group)
    return group


def invalidate_group(db: Session, trip_id: int) -> None:
    """Set is_active=False on the split group. Called by cancel_trip."""
    groups = (
        db.query(SplitGroup)
        .filter(SplitGroup.trip_id == trip_id, SplitGroup.is_active == True)  # noqa: E712
        .all()
    )
    for g in groups:
        g.is_active = False
    db.commit()


# ---------------------------------------------------------------------------
# Co-organizer management
# ---------------------------------------------------------------------------


def add_co_organizer(
    db: Session, trip_id: int, family_id: int, user_id: int, target_user_id: int
) -> TripCoOrganizer:
    """Add a co-organizer to a trip. Only the trip organizer can do this."""
    trip = _get_trip(db, trip_id, family_id)

    if trip.user_id != user_id:
        raise AppError(ErrorCode.CO_ORGANIZER_NOT_ALLOWED)

    count = db.query(TripCoOrganizer).filter(TripCoOrganizer.trip_id == trip_id).count()
    if count >= _MAX_CO_ORGANIZERS:
        raise AppError(ErrorCode.CO_ORGANIZER_LIMIT)

    # Check not already a co-organizer
    existing = (
        db.query(TripCoOrganizer)
        .filter(
            TripCoOrganizer.trip_id == trip_id,
            TripCoOrganizer.user_id == target_user_id,
        )
        .first()
    )
    if existing:
        db.refresh(existing)
        return existing

    co = TripCoOrganizer(trip_id=trip_id, user_id=target_user_id)
    db.add(co)
    db.commit()
    db.refresh(co)
    return co


def remove_co_organizer(
    db: Session, trip_id: int, family_id: int, user_id: int, target_user_id: int
) -> None:
    """Remove a co-organizer. Only the trip organizer can do this."""
    trip = _get_trip(db, trip_id, family_id)

    if trip.user_id != user_id:
        raise AppError(ErrorCode.CO_ORGANIZER_NOT_ALLOWED)

    co = (
        db.query(TripCoOrganizer)
        .filter(
            TripCoOrganizer.trip_id == trip_id,
            TripCoOrganizer.user_id == target_user_id,
        )
        .first()
    )
    if not co:
        raise AppError(ErrorCode.SPLIT_PARTICIPANT_NOT_FOUND)

    db.delete(co)
    db.commit()


def is_organizer_or_co(db: Session, trip_id: int, user_id: int) -> bool:
    """Check if user is the trip organizer or a co-organizer."""
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        return False
    if trip.user_id == user_id:
        return True
    co = (
        db.query(TripCoOrganizer)
        .filter(
            TripCoOrganizer.trip_id == trip_id,
            TripCoOrganizer.user_id == user_id,
        )
        .first()
    )
    return co is not None
