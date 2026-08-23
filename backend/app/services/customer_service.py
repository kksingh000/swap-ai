"""Customer lookup / creation, plus the do-not-call gate."""
import random
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models import Customer, DoNotCallEntry


def normalise_phone(phone: str) -> str:
    cleaned = "".join(ch for ch in (phone or "") if ch.isdigit() or ch == "+")
    if cleaned and not cleaned.startswith("+") and len(cleaned) == 10:
        cleaned = f"+91{cleaned}"
    return cleaned


def get_or_create(
    db: Session,
    phone_number: str,
    name: Optional[str] = None,
    language: str = "english",
) -> Customer:
    phone = normalise_phone(phone_number)
    customer = db.query(Customer).filter(Customer.phone_number == phone).first()
    if customer is None:
        customer = Customer(phone_number=phone, name=name, preferred_language=language)
        db.add(customer)
        db.commit()
        db.refresh(customer)
    else:
        changed = False
        if name and not customer.name:
            customer.name = name
            changed = True
        if language and customer.preferred_language != language:
            customer.preferred_language = language
            changed = True
        if changed:
            db.commit()
    return customer


def is_do_not_call(db: Session, phone_number: str) -> Tuple[bool, Optional[str]]:
    phone = normalise_phone(phone_number)
    customer = db.query(Customer).filter(Customer.phone_number == phone).first()
    if customer and customer.do_not_call:
        return True, "Customer is marked do-not-call"
    entry = db.query(DoNotCallEntry).filter(DoNotCallEntry.phone_number == phone).first()
    if entry:
        return True, entry.reason or "Number is on the do-not-call list"
    return False, None


def demo_phone() -> str:
    return f"+9198{random.randint(10000000, 99999999)}"
