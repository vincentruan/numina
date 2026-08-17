from decimal import Decimal

from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.rental_contract import RentalContract
from apps.backend.app.models.user import User
from apps.backend.app.schemas.rental_contract import (
    RentalContractCreate,
    RentalContractSummary,
    RentalContractUpdate,
)
from packages.db.models.asset import Asset


def list_rental_contracts(
    db: Session,
    user: User,
    role: str | None = None,
    active_only: bool | None = None,
) -> list[RentalContract]:
    query = db.query(RentalContract).filter(RentalContract.family_id == user.family_id)
    if role is not None:
        query = query.filter(RentalContract.role == role)
    if active_only is not None:
        query = query.filter(RentalContract.is_active == active_only)
    return query.order_by(RentalContract.created_at.desc()).all()


def get_rental_contract(db: Session, user: User, contract_id: str) -> RentalContract:
    contract = (
        db.query(RentalContract)
        .filter(RentalContract.id == contract_id, RentalContract.family_id == user.family_id)
        .first()
    )
    if not contract:
        raise AppError(ErrorCode.RENTAL_CONTRACT_NOT_FOUND)
    return contract


def _validate_linked_asset(db: Session, user: User, asset_id: int | None) -> None:
    """Validate linked_asset_id belongs to the user's family (landlord role only)."""
    if asset_id is None:
        return
    asset = (
        db.query(Asset)
        .filter(Asset.id == asset_id, Asset.family_id == user.family_id)
        .first()
    )
    if not asset:
        raise AppError(ErrorCode.RENTAL_CONTRACT_INVALID_ASSET)


def create_rental_contract(
    db: Session, user: User, req: RentalContractCreate
) -> RentalContract:
    # Validate linked_asset_id for landlord role
    if req.role == "landlord":
        _validate_linked_asset(db, user, req.linked_asset_id)
    elif req.role == "tenant" and req.linked_asset_id is not None:
        # Tenant contracts should not have linked_asset_id
        req.linked_asset_id = None

    contract = RentalContract(
        user_id=user.id,
        family_id=user.family_id,
        role=req.role,
        monthly_rent=req.monthly_rent,
        deposit=req.deposit,
        start_date=req.start_date,
        end_date=req.end_date,
        linked_asset_id=req.linked_asset_id,
        counterparty=req.counterparty,
        notes=req.notes,
        currency=req.currency,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract


def update_rental_contract(
    db: Session, user: User, contract_id: str, req: RentalContractUpdate
) -> RentalContract:
    contract = get_rental_contract(db, user, contract_id)
    update_data = req.model_dump(exclude_unset=True)

    # Validate linked_asset_id if being updated
    if "linked_asset_id" in update_data:
        _validate_linked_asset(db, user, update_data["linked_asset_id"])

    for key, value in update_data.items():
        setattr(contract, key, value)
    db.commit()
    db.refresh(contract)
    return contract


def delete_rental_contract(db: Session, user: User, contract_id: str) -> None:
    """Soft delete — set is_active=False."""
    contract = get_rental_contract(db, user, contract_id)
    contract.is_active = False
    db.commit()


def get_rental_summary(db: Session, user: User) -> RentalContractSummary:
    """Aggregate active rental contracts for the user's family."""
    contracts = (
        db.query(RentalContract)
        .filter(
            RentalContract.family_id == user.family_id,
            RentalContract.is_active == True,  # noqa: E712
        )
        .all()
    )

    income = Decimal("0")
    expense = Decimal("0")
    total_deposit = Decimal("0")

    for c in contracts:
        total_deposit += c.deposit or Decimal("0")
        if c.role == "landlord":
            income += c.monthly_rent
        else:
            expense += c.monthly_rent

    net = income - expense

    return RentalContractSummary(
        monthly_income=str(income.quantize(Decimal("0.01"))),
        monthly_expense=str(expense.quantize(Decimal("0.01"))),
        net_cash_flow=str(net.quantize(Decimal("0.01"))),
        total_deposit=str(total_deposit.quantize(Decimal("0.01"))),
    )
