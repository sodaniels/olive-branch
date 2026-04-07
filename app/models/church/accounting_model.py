# app/models/church/accounting_model.py

from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from bson import ObjectId
from decimal import Decimal

from ...models.base_model import BaseModel
from ...extensions.db import db
from ...utils.crypt import encrypt_data, decrypt_data, hash_data
from ...utils.logger import Log


# ═══════════════════════════════════════════════════════════════
# CHART OF ACCOUNTS
# ═══════════════════════════════════════════════════════════════

class Account(BaseModel):
    """Chart of Accounts entry. Hierarchical via parent_account_id."""

    collection_name = "accounts"

    TYPE_ASSET = "Asset"
    TYPE_LIABILITY = "Liability"
    TYPE_EQUITY = "Equity"
    TYPE_INCOME = "Income"
    TYPE_EXPENSE = "Expense"
    ACCOUNT_TYPES = [TYPE_ASSET, TYPE_LIABILITY, TYPE_EQUITY, TYPE_INCOME, TYPE_EXPENSE]

    SUB_TYPES = {
        "Asset": ["Cash", "Bank", "Accounts Receivable", "Fixed Asset", "Other Asset"],
        "Liability": ["Accounts Payable", "Credit Card", "Loan", "Other Liability"],
        "Equity": ["Retained Earnings", "Opening Balance", "Other Equity"],
        "Income": ["Tithes", "Offerings", "Donations", "Event Income", "Interest", "Other Income"],
        "Expense": ["Salaries", "Rent", "Utilities", "Supplies", "Ministry", "Missions", "Maintenance", "Transport", "Other Expense"],
    }

    FIELDS_TO_DECRYPT = ["name", "description"]

    def __init__(self, name, account_type, account_code=None, sub_type=None,
                 description=None, parent_account_id=None, fund_id=None,
                 is_active=True, opening_balance=0.0, currency="GBP",
                 branch_id=None, user_id=None, user__id=None, business_id=None, **kw):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kw)
        self.business_id = ObjectId(business_id) if business_id else None

        if name:
            self.name = encrypt_data(name)
            self.hashed_name = hash_data(name.strip().lower())
        if description:
            self.description = encrypt_data(description)

        self.account_type = account_type
        self.hashed_account_type = hash_data(account_type.strip())
        if sub_type: self.sub_type = sub_type
        if account_code:
            self.account_code = account_code
            self.hashed_account_code = hash_data(account_code.strip())
        if parent_account_id: self.parent_account_id = ObjectId(parent_account_id)
        if fund_id: self.fund_id = ObjectId(fund_id)
        if branch_id: self.branch_id = ObjectId(branch_id)

        self.is_active = bool(is_active)
        self.opening_balance = float(opening_balance)
        self.current_balance = float(opening_balance)
        self.currency = currency

        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        doc = {
            "business_id": self.business_id,
            "name": getattr(self, "name", None), "hashed_name": getattr(self, "hashed_name", None),
            "description": getattr(self, "description", None),
            "account_type": getattr(self, "account_type", None), "hashed_account_type": getattr(self, "hashed_account_type", None),
            "sub_type": getattr(self, "sub_type", None),
            "account_code": getattr(self, "account_code", None), "hashed_account_code": getattr(self, "hashed_account_code", None),
            "parent_account_id": getattr(self, "parent_account_id", None),
            "fund_id": getattr(self, "fund_id", None),
            "branch_id": getattr(self, "branch_id", None),
            "is_active": getattr(self, "is_active", None),
            "opening_balance": getattr(self, "opening_balance", None),
            "current_balance": getattr(self, "current_balance", None),
            "currency": getattr(self, "currency", None),
            "created_at": self.created_at, "updated_at": self.updated_at,
        }
        return {k: v for k, v in doc.items() if v is not None}

    @staticmethod
    def _safe_decrypt(v):
        if v is None: return None
        if not isinstance(v, str): return v
        try: return decrypt_data(v)
        except: return v

    @classmethod
    def _normalise(cls, doc):
        if not doc: return None
        for f in ["_id", "business_id", "parent_account_id", "fund_id", "branch_id"]:
            if doc.get(f): doc[f] = str(doc[f])
        for f in cls.FIELDS_TO_DECRYPT:
            if f in doc: doc[f] = cls._safe_decrypt(doc[f])
        for h in ["hashed_name", "hashed_account_type", "hashed_account_code"]:
            doc.pop(h, None)
        return doc

    @classmethod
    def get_by_id(cls, account_id, business_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"_id": ObjectId(account_id)}
            if business_id: q["business_id"] = ObjectId(business_id)
            return cls._normalise(c.find_one(q))
        except Exception as e:
            Log.error(f"[Account.get_by_id] {e}"); return None

    @classmethod
    def get_all(cls, business_id, account_type=None, fund_id=None, is_active=True, page=1, per_page=100):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id)}
            if account_type: q["hashed_account_type"] = hash_data(account_type.strip())
            if fund_id: q["fund_id"] = ObjectId(fund_id)
            if is_active is not None: q["is_active"] = is_active
            total = c.count_documents(q)
            cursor = c.find(q).sort("account_code", 1).skip((page-1)*per_page).limit(per_page)
            items = [cls._normalise(d) for d in cursor]
            return {"accounts": items, "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"[Account.get_all] {e}")
            return {"accounts": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_children(cls, business_id, parent_account_id):
        try:
            c = db.get_collection(cls.collection_name)
            cursor = c.find({"business_id": ObjectId(business_id), "parent_account_id": ObjectId(parent_account_id)}).sort("account_code", 1)
            return [cls._normalise(d) for d in cursor]
        except Exception as e:
            Log.error(f"[Account.get_children] {e}"); return []

    @classmethod
    def adjust_balance(cls, account_id, business_id, amount):
        """Increment (positive) or decrement (negative) the current_balance."""
        try:
            c = db.get_collection(cls.collection_name)
            c.update_one(
                {"_id": ObjectId(account_id), "business_id": ObjectId(business_id)},
                {"$inc": {"current_balance": float(amount)}, "$set": {"updated_at": datetime.utcnow()}},
            )
        except Exception as e:
            Log.error(f"[Account.adjust_balance] {e}")

    @classmethod
    def update(cls, account_id, business_id, **updates):
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}
        if "name" in updates and updates["name"]:
            p = updates["name"]; updates["name"] = encrypt_data(p); updates["hashed_name"] = hash_data(p.strip().lower())
        if "description" in updates and updates["description"]:
            updates["description"] = encrypt_data(updates["description"])
        if "account_type" in updates and updates["account_type"]:
            updates["hashed_account_type"] = hash_data(updates["account_type"].strip())
        if "account_code" in updates and updates["account_code"]:
            updates["hashed_account_code"] = hash_data(updates["account_code"].strip())
        for oid in ["parent_account_id", "fund_id", "branch_id"]:
            if oid in updates and updates[oid]: updates[oid] = ObjectId(updates[oid])
        return super().update(account_id, business_id, **updates)

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("hashed_account_type", 1), ("account_code", 1)])
            c.create_index([("business_id", 1), ("hashed_name", 1)])
            c.create_index([("business_id", 1), ("hashed_account_code", 1)], unique=True)
            c.create_index([("business_id", 1), ("parent_account_id", 1)])
            c.create_index([("business_id", 1), ("fund_id", 1)])
            return True
        except Exception as e:
            Log.error(f"[Account.create_indexes] {e}"); return False


# ═══════════════════════════════════════════════════════════════
# FUND
# ═══════════════════════════════════════════════════════════════

class Fund(BaseModel):
    """Fund for fund-specific accounting (General, Building, Missions, etc.)."""

    collection_name = "funds"
    FIELDS_TO_DECRYPT = ["name", "description"]

    def __init__(self, name, description=None, fund_code=None, is_active=True,
                 target_amount=None, currency="GBP", branch_id=None,
                 user_id=None, user__id=None, business_id=None, **kw):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kw)
        self.business_id = ObjectId(business_id) if business_id else None
        if name: self.name = encrypt_data(name); self.hashed_name = hash_data(name.strip().lower())
        if description: self.description = encrypt_data(description)
        if fund_code: self.fund_code = fund_code
        self.is_active = bool(is_active)
        self.current_balance = 0.0
        if target_amount is not None: self.target_amount = float(target_amount)
        self.currency = currency
        if branch_id: self.branch_id = ObjectId(branch_id)
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        doc = {
            "business_id": self.business_id,
            "name": getattr(self, "name", None), "hashed_name": getattr(self, "hashed_name", None),
            "description": getattr(self, "description", None),
            "fund_code": getattr(self, "fund_code", None),
            "is_active": getattr(self, "is_active", None),
            "current_balance": getattr(self, "current_balance", None),
            "target_amount": getattr(self, "target_amount", None),
            "currency": getattr(self, "currency", None),
            "branch_id": getattr(self, "branch_id", None),
            "created_at": self.created_at, "updated_at": self.updated_at,
        }
        return {k: v for k, v in doc.items() if v is not None}

    @staticmethod
    def _safe_decrypt(v):
        if v is None: return None
        if not isinstance(v, str): return v
        try: return decrypt_data(v)
        except: return v

    @classmethod
    def _normalise(cls, doc):
        if not doc: return None
        for f in ["_id", "business_id", "branch_id"]: 
            if doc.get(f): doc[f] = str(doc[f])
        for f in cls.FIELDS_TO_DECRYPT:
            if f in doc: doc[f] = cls._safe_decrypt(doc[f])
        doc.pop("hashed_name", None)
        ta = doc.get("target_amount")
        cb = doc.get("current_balance", 0)
        if ta and ta > 0: doc["progress_pct"] = round((cb / ta) * 100, 1)
        return doc

    @classmethod
    def get_by_id(cls, fund_id, business_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"_id": ObjectId(fund_id)}
            if business_id: q["business_id"] = ObjectId(business_id)
            return cls._normalise(c.find_one(q))
        except Exception as e: Log.error(f"[Fund.get_by_id] {e}"); return None

    @classmethod
    def get_all(cls, business_id, is_active=True, page=1, per_page=50):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id)}
            if is_active is not None: q["is_active"] = is_active
            total = c.count_documents(q)
            cursor = c.find(q).sort("created_at", -1).skip((page-1)*per_page).limit(per_page)
            items = [cls._normalise(d) for d in cursor]
            return {"funds": items, "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page, "per_page": per_page}
        except Exception as e: Log.error(f"[Fund.get_all] {e}")
        return {"funds": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def adjust_balance(cls, fund_id, business_id, amount):
        try:
            c = db.get_collection(cls.collection_name)
            c.update_one({"_id": ObjectId(fund_id), "business_id": ObjectId(business_id)},
                         {"$inc": {"current_balance": float(amount)}, "$set": {"updated_at": datetime.utcnow()}})
        except Exception as e: Log.error(f"[Fund.adjust_balance] {e}")

    @classmethod
    def get_summary(cls, business_id):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id), "is_active": True}
            cursor = c.find(q).sort("created_at", 1)
            funds = [cls._normalise(d) for d in cursor]
            total_balance = sum(f.get("current_balance", 0) for f in funds)
            return {"funds": funds, "total_funds": len(funds), "total_balance": round(total_balance, 2)}
        except Exception as e: Log.error(f"[Fund.get_summary] {e}")
        return {"funds": [], "total_funds": 0, "total_balance": 0}

    @classmethod
    def update(cls, fund_id, business_id, **updates):
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}
        if "name" in updates and updates["name"]:
            p = updates["name"]; updates["name"] = encrypt_data(p); updates["hashed_name"] = hash_data(p.strip().lower())
        if "description" in updates and updates["description"]: updates["description"] = encrypt_data(updates["description"])
        for oid in ["branch_id"]:
            if oid in updates and updates[oid]: updates[oid] = ObjectId(updates[oid])
        return super().update(fund_id, business_id, **updates)

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("hashed_name", 1)])
            c.create_index([("business_id", 1), ("is_active", 1)])
            return True
        except Exception as e: Log.error(f"[Fund.create_indexes] {e}"); return False


# ═══════════════════════════════════════════════════════════════
# CATEGORY & PAYEE
# ═══════════════════════════════════════════════════════════════

class Category(BaseModel):
    """Transaction category (e.g. 'Pastoral Salary', 'Electricity', 'Guest Speaker')."""
    collection_name = "categories"

    def __init__(self, name, category_type="Expense", description=None, parent_category_id=None,
                 is_active=True, user_id=None, user__id=None, business_id=None, **kw):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kw)
        self.business_id = ObjectId(business_id) if business_id else None
        if name: self.name = encrypt_data(name); self.hashed_name = hash_data(name.strip().lower())
        self.category_type = category_type  # "Income" or "Expense"
        if description: self.description = encrypt_data(description)
        if parent_category_id: self.parent_category_id = ObjectId(parent_category_id)
        self.is_active = bool(is_active)
        self.created_at = datetime.utcnow(); self.updated_at = datetime.utcnow()

    def to_dict(self):
        doc = {"business_id": self.business_id, "name": getattr(self,"name",None), "hashed_name": getattr(self,"hashed_name",None),
               "category_type": self.category_type, "description": getattr(self,"description",None),
               "parent_category_id": getattr(self,"parent_category_id",None), "is_active": self.is_active,
               "created_at": self.created_at, "updated_at": self.updated_at}
        return {k:v for k,v in doc.items() if v is not None}

    @classmethod
    def _normalise(cls, doc):
        if not doc: return None
        for f in ["_id","business_id","parent_category_id"]:
            if doc.get(f): doc[f] = str(doc[f])
        for f in ["name","description"]:
            if f in doc and isinstance(doc[f], str):
                try: doc[f] = decrypt_data(doc[f])
                except: pass
        doc.pop("hashed_name", None)
        return doc

    @classmethod
    def get_by_id(cls, cat_id, business_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"_id": ObjectId(cat_id)};
            if business_id: q["business_id"] = ObjectId(business_id)
            return cls._normalise(c.find_one(q))
        except: return None

    @classmethod
    def get_all(cls, business_id, category_type=None, page=1, per_page=100):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id), "is_active": True}
            if category_type: q["category_type"] = category_type
            total = c.count_documents(q)
            cursor = c.find(q).sort("created_at", -1).skip((page-1)*per_page).limit(per_page)
            return {"categories": [cls._normalise(d) for d in cursor], "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page, "per_page": per_page}
        except: return {"categories": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("hashed_name", 1)])
            c.create_index([("business_id", 1), ("category_type", 1)])
            return True
        except: return False


class Payee(BaseModel):
    """Payee / vendor (e.g. 'UK Power Networks', 'Pastor Mensah', 'Office Supplies Ltd')."""
    collection_name = "payees"

    def __init__(self, name, payee_type="Vendor", email=None, phone=None,
                 address=None, bank_details=None, is_active=True,
                 user_id=None, user__id=None, business_id=None, **kw):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kw)
        self.business_id = ObjectId(business_id) if business_id else None
        if name: self.name = encrypt_data(name); self.hashed_name = hash_data(name.strip().lower())
        self.payee_type = payee_type  # "Vendor", "Employee", "Ministry", "Other"
        if email: self.email = encrypt_data(email)
        if phone: self.phone = encrypt_data(phone)
        if address: self.address = encrypt_data(address)
        if bank_details: self.bank_details = encrypt_data(str(bank_details))
        self.is_active = bool(is_active)
        self.created_at = datetime.utcnow(); self.updated_at = datetime.utcnow()

    def to_dict(self):
        doc = {"business_id": self.business_id, "name": getattr(self,"name",None), "hashed_name": getattr(self,"hashed_name",None),
               "payee_type": self.payee_type, "email": getattr(self,"email",None), "phone": getattr(self,"phone",None),
               "address": getattr(self,"address",None), "bank_details": getattr(self,"bank_details",None),
               "is_active": self.is_active, "created_at": self.created_at, "updated_at": self.updated_at}
        return {k:v for k,v in doc.items() if v is not None}

    @classmethod
    def _normalise(cls, doc):
        if not doc: return None
        for f in ["_id","business_id"]:
            if doc.get(f): doc[f] = str(doc[f])
        for f in ["name","email","phone","address","bank_details"]:
            if f in doc and isinstance(doc[f], str):
                try: doc[f] = decrypt_data(doc[f])
                except: pass
        doc.pop("hashed_name", None)
        return doc

    @classmethod
    def get_by_id(cls, payee_id, business_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"_id": ObjectId(payee_id)}
            if business_id: q["business_id"] = ObjectId(business_id)
            return cls._normalise(c.find_one(q))
        except: return None

    @classmethod
    def get_all(cls, business_id, payee_type=None, page=1, per_page=100):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id), "is_active": True}
            if payee_type: q["payee_type"] = payee_type
            total = c.count_documents(q)
            cursor = c.find(q).sort("created_at", -1).skip((page-1)*per_page).limit(per_page)
            return {"payees": [cls._normalise(d) for d in cursor], "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page, "per_page": per_page}
        except: return {"payees": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("hashed_name", 1)])
            c.create_index([("business_id", 1), ("payee_type", 1)])
            return True
        except: return False


# ═══════════════════════════════════════════════════════════════
# TRANSACTION
# ═══════════════════════════════════════════════════════════════

class Transaction(BaseModel):
    """
    Financial transaction (income or expense).
    Double-entry: each transaction debits one account and credits another.
    """

    collection_name = "transactions"

    TYPE_INCOME = "Income"
    TYPE_EXPENSE = "Expense"
    TYPE_TRANSFER = "Transfer"
    TRANSACTION_TYPES = [TYPE_INCOME, TYPE_EXPENSE, TYPE_TRANSFER]

    STATUS_PENDING = "Pending"
    STATUS_CLEARED = "Cleared"
    STATUS_RECONCILED = "Reconciled"
    STATUS_VOIDED = "Voided"
    STATUSES = [STATUS_PENDING, STATUS_CLEARED, STATUS_RECONCILED, STATUS_VOIDED]

    PAYMENT_METHODS = ["Cash", "Cheque", "Bank Transfer", "Card", "Mobile Money", "Online", "Direct Debit", "Other"]

    FIELDS_TO_DECRYPT = ["description", "memo"]

    def __init__(self, transaction_type, amount, transaction_date,
                 debit_account_id=None, credit_account_id=None,
                 fund_id=None, category_id=None, payee_id=None,
                 description=None, memo=None, reference_number=None,
                 payment_method=None, cheque_number=None,
                 status="Cleared", currency="GBP",
                 branch_id=None, is_recurring=False, recurring_rule=None,
                 attachment_urls=None,
                 # Bank import fields
                 bank_transaction_id=None, is_bank_imported=False,
                 user_id=None, user__id=None, business_id=None, **kw):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kw)
        self.business_id = ObjectId(business_id) if business_id else None

        self.transaction_type = transaction_type
        self.hashed_transaction_type = hash_data(transaction_type.strip())
        self.amount = round(float(amount), 2)
        self.transaction_date = transaction_date

        if debit_account_id: self.debit_account_id = ObjectId(debit_account_id)
        if credit_account_id: self.credit_account_id = ObjectId(credit_account_id)
        if fund_id: self.fund_id = ObjectId(fund_id)
        if category_id: self.category_id = ObjectId(category_id)
        if payee_id: self.payee_id = ObjectId(payee_id)

        if description: self.description = encrypt_data(description)
        if memo: self.memo = encrypt_data(memo)
        if reference_number: self.reference_number = reference_number
        if payment_method: self.payment_method = payment_method
        if cheque_number: self.cheque_number = cheque_number

        self.status = status
        self.hashed_status = hash_data(status.strip())
        self.currency = currency

        if branch_id: self.branch_id = ObjectId(branch_id)
        self.is_recurring = bool(is_recurring)
        if recurring_rule: self.recurring_rule = recurring_rule
        if attachment_urls: self.attachment_urls = attachment_urls

        if bank_transaction_id: self.bank_transaction_id = bank_transaction_id
        self.is_bank_imported = bool(is_bank_imported)

        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        doc = {
            "business_id": self.business_id,
            "transaction_type": self.transaction_type, "hashed_transaction_type": self.hashed_transaction_type,
            "amount": self.amount, "transaction_date": self.transaction_date,
            "debit_account_id": getattr(self,"debit_account_id",None),
            "credit_account_id": getattr(self,"credit_account_id",None),
            "fund_id": getattr(self,"fund_id",None),
            "category_id": getattr(self,"category_id",None),
            "payee_id": getattr(self,"payee_id",None),
            "description": getattr(self,"description",None),
            "memo": getattr(self,"memo",None),
            "reference_number": getattr(self,"reference_number",None),
            "payment_method": getattr(self,"payment_method",None),
            "cheque_number": getattr(self,"cheque_number",None),
            "status": self.status, "hashed_status": self.hashed_status,
            "currency": self.currency,
            "branch_id": getattr(self,"branch_id",None),
            "is_recurring": self.is_recurring,
            "recurring_rule": getattr(self,"recurring_rule",None),
            "attachment_urls": getattr(self,"attachment_urls",None),
            "bank_transaction_id": getattr(self,"bank_transaction_id",None),
            "is_bank_imported": self.is_bank_imported,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }
        return {k:v for k,v in doc.items() if v is not None}

    @classmethod
    def _normalise(cls, doc):
        if not doc: return None
        for f in ["_id","business_id","debit_account_id","credit_account_id","fund_id","category_id","payee_id","branch_id"]:
            if doc.get(f): doc[f] = str(doc[f])
        for f in cls.FIELDS_TO_DECRYPT:
            if f in doc:
                try: doc[f] = decrypt_data(doc[f])
                except: pass
        for h in ["hashed_transaction_type","hashed_status"]: doc.pop(h, None)
        return doc

    @classmethod
    def get_by_id(cls, txn_id, business_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"_id": ObjectId(txn_id)}
            if business_id: q["business_id"] = ObjectId(business_id)
            return cls._normalise(c.find_one(q))
        except Exception as e: Log.error(f"[Transaction.get_by_id] {e}"); return None

    @classmethod
    def get_all(cls, business_id, page=1, per_page=50, transaction_type=None, status=None,
                fund_id=None, account_id=None, category_id=None, payee_id=None,
                start_date=None, end_date=None, branch_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id)}
            if transaction_type: q["hashed_transaction_type"] = hash_data(transaction_type.strip())
            if status: q["hashed_status"] = hash_data(status.strip())
            if fund_id: q["fund_id"] = ObjectId(fund_id)
            if account_id: q["$or"] = [{"debit_account_id": ObjectId(account_id)}, {"credit_account_id": ObjectId(account_id)}]
            if category_id: q["category_id"] = ObjectId(category_id)
            if payee_id: q["payee_id"] = ObjectId(payee_id)
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            if start_date: q.setdefault("transaction_date",{})["$gte"] = start_date
            if end_date: q.setdefault("transaction_date",{})["$lte"] = end_date

            total = c.count_documents(q)
            cursor = c.find(q).sort("transaction_date", -1).skip((page-1)*per_page).limit(per_page)
            items = [cls._normalise(d) for d in cursor]
            return {"transactions": items, "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page, "per_page": per_page}
        except Exception as e: Log.error(f"[Transaction.get_all] {e}")
        return {"transactions": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def void(cls, txn_id, business_id):
        """Void a transaction and reverse account/fund balance changes."""
        try:
            txn = cls.get_by_id(txn_id, business_id)
            if not txn or txn.get("status") == "Voided": return False

            amount = txn.get("amount", 0)
            # Reverse balances
            if txn.get("debit_account_id"):
                Account.adjust_balance(txn["debit_account_id"], business_id, -amount)
            if txn.get("credit_account_id"):
                Account.adjust_balance(txn["credit_account_id"], business_id, amount)
            if txn.get("fund_id"):
                reversal = -amount if txn.get("transaction_type") == cls.TYPE_INCOME else amount
                Fund.adjust_balance(txn["fund_id"], business_id, reversal)

            c = db.get_collection(cls.collection_name)
            c.update_one(
                {"_id": ObjectId(txn_id), "business_id": ObjectId(business_id)},
                {"$set": {"status": "Voided", "hashed_status": hash_data("Voided"), "updated_at": datetime.utcnow()}},
            )
            return True
        except Exception as e: Log.error(f"[Transaction.void] {e}"); return False

    @classmethod
    def get_income_expense_statement(cls, business_id, start_date, end_date, fund_id=None, branch_id=None):
        """Income & Expense statement for a period."""
        try:
            c = db.get_collection(cls.collection_name)
            base = {
                "business_id": ObjectId(business_id),
                "transaction_date": {"$gte": start_date, "$lte": end_date},
                "hashed_status": {"$ne": hash_data("Voided")},
            }
            if fund_id: base["fund_id"] = ObjectId(fund_id)
            if branch_id: base["branch_id"] = ObjectId(branch_id)

            pipeline = [
                {"$match": base},
                {"$group": {"_id": "$transaction_type", "total": {"$sum": "$amount"}, "count": {"$sum": 1}}},
            ]
            results = {r["_id"]: {"total": round(r["total"], 2), "count": r["count"]} for r in c.aggregate(pipeline)}

            income = results.get("Income", {"total": 0, "count": 0})
            expense = results.get("Expense", {"total": 0, "count": 0})
            net = round(income["total"] - expense["total"], 2)

            return {
                "period": {"start": start_date, "end": end_date},
                "income": income, "expense": expense,
                "net_income": net,
            }
        except Exception as e: Log.error(f"[Transaction.income_expense] {e}"); return {}

    @classmethod
    def get_balance_sheet(cls, business_id, as_of_date, branch_id=None):
        """Balance sheet as of a specific date."""
        try:
            accounts_coll = db.get_collection(Account.collection_name)
            q = {"business_id": ObjectId(business_id), "is_active": True}
            if branch_id: q["branch_id"] = ObjectId(branch_id)

            cursor = accounts_coll.find(q)
            assets, liabilities, equity = 0, 0, 0
            asset_accounts, liability_accounts, equity_accounts = [], [], []

            for a in cursor:
                norm = Account._normalise(dict(a))
                bal = norm.get("current_balance", 0)
                at = norm.get("account_type")
                entry = {"account_id": norm["_id"], "name": norm.get("name"), "code": norm.get("account_code"), "balance": round(bal, 2)}

                if at == "Asset":
                    assets += bal; asset_accounts.append(entry)
                elif at == "Liability":
                    liabilities += bal; liability_accounts.append(entry)
                elif at == "Equity":
                    equity += bal; equity_accounts.append(entry)

            return {
                "as_of_date": as_of_date,
                "assets": {"total": round(assets, 2), "accounts": asset_accounts},
                "liabilities": {"total": round(liabilities, 2), "accounts": liability_accounts},
                "equity": {"total": round(equity, 2), "accounts": equity_accounts},
                "total_liabilities_and_equity": round(liabilities + equity, 2),
                "balanced": round(assets, 2) == round(liabilities + equity, 2),
            }
        except Exception as e: Log.error(f"[Transaction.balance_sheet] {e}"); return {}

    @classmethod
    def get_fund_summary(cls, business_id, start_date=None, end_date=None):
        """Summary of income/expense per fund."""
        try:
            c = db.get_collection(cls.collection_name)
            match = {"business_id": ObjectId(business_id), "hashed_status": {"$ne": hash_data("Voided")}}
            if start_date: match.setdefault("transaction_date",{})["$gte"] = start_date
            if end_date: match.setdefault("transaction_date",{})["$lte"] = end_date

            pipeline = [
                {"$match": {**match, "fund_id": {"$exists": True}}},
                {"$group": {
                    "_id": {"fund_id": "$fund_id", "type": "$transaction_type"},
                    "total": {"$sum": "$amount"}, "count": {"$sum": 1},
                }},
            ]
            results = list(c.aggregate(pipeline))

            fund_data = {}
            for r in results:
                fid = str(r["_id"]["fund_id"])
                tt = r["_id"]["type"]
                fund_data.setdefault(fid, {"income": 0, "expense": 0, "income_count": 0, "expense_count": 0})
                if tt == "Income":
                    fund_data[fid]["income"] = round(r["total"], 2); fund_data[fid]["income_count"] = r["count"]
                elif tt == "Expense":
                    fund_data[fid]["expense"] = round(r["total"], 2); fund_data[fid]["expense_count"] = r["count"]

            for fid, data in fund_data.items():
                data["net"] = round(data["income"] - data["expense"], 2)
                fund = Fund.get_by_id(fid, business_id)
                data["fund_name"] = fund.get("name") if fund else fid

            return {"fund_summary": list(fund_data.values()), "fund_count": len(fund_data)}
        except Exception as e: Log.error(f"[Transaction.fund_summary] {e}"); return {}

    @classmethod
    def update(cls, txn_id, business_id, **updates):
        updates["updated_at"] = datetime.utcnow()
        updates = {k:v for k,v in updates.items() if v is not None}
        if "transaction_type" in updates: updates["hashed_transaction_type"] = hash_data(updates["transaction_type"].strip())
        if "status" in updates: updates["hashed_status"] = hash_data(updates["status"].strip())
        for f in ["description","memo"]:
            if f in updates and updates[f]: updates[f] = encrypt_data(updates[f])
        for oid in ["debit_account_id","credit_account_id","fund_id","category_id","payee_id","branch_id"]:
            if oid in updates and updates[oid]: updates[oid] = ObjectId(updates[oid])
        return super().update(txn_id, business_id, **updates)

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("transaction_date", -1)])
            c.create_index([("business_id", 1), ("hashed_transaction_type", 1)])
            c.create_index([("business_id", 1), ("hashed_status", 1)])
            c.create_index([("business_id", 1), ("fund_id", 1)])
            c.create_index([("business_id", 1), ("category_id", 1)])
            c.create_index([("business_id", 1), ("payee_id", 1)])
            c.create_index([("business_id", 1), ("debit_account_id", 1)])
            c.create_index([("business_id", 1), ("credit_account_id", 1)])
            c.create_index([("business_id", 1), ("branch_id", 1)])
            c.create_index([("business_id", 1), ("bank_transaction_id", 1)])
            return True
        except Exception as e: Log.error(f"[Transaction.create_indexes] {e}"); return False


# ═══════════════════════════════════════════════════════════════
# BUDGET
# ═══════════════════════════════════════════════════════════════

class Budget(BaseModel):
    """Annual/periodic budget with line items and progress tracking."""
    collection_name = "budgets"

    PERIOD_ANNUAL = "Annual"
    PERIOD_QUARTERLY = "Quarterly"
    PERIOD_MONTHLY = "Monthly"
    PERIODS = [PERIOD_ANNUAL, PERIOD_QUARTERLY, PERIOD_MONTHLY]

    FIELDS_TO_DECRYPT = ["name", "description"]

    def __init__(self, name, fiscal_year, period="Annual", start_date=None, end_date=None,
                 description=None, fund_id=None, branch_id=None,
                 line_items=None, status="Active", currency="GBP",
                 user_id=None, user__id=None, business_id=None, **kw):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kw)
        self.business_id = ObjectId(business_id) if business_id else None
        if name: self.name = encrypt_data(name); self.hashed_name = hash_data(name.strip().lower())
        if description: self.description = encrypt_data(description)
        self.fiscal_year = fiscal_year
        self.period = period
        if start_date: self.start_date = start_date
        if end_date: self.end_date = end_date
        if fund_id: self.fund_id = ObjectId(fund_id)
        if branch_id: self.branch_id = ObjectId(branch_id)
        self.status = status
        self.currency = currency
        # line_items: [{"category_id":"...","category_name":"...","budgeted_amount":1000,"type":"Income"/"Expense"}]
        self.line_items = line_items or []
        self.created_at = datetime.utcnow(); self.updated_at = datetime.utcnow()

    def to_dict(self):
        doc = {
            "business_id": self.business_id,
            "name": getattr(self,"name",None), "hashed_name": getattr(self,"hashed_name",None),
            "description": getattr(self,"description",None),
            "fiscal_year": self.fiscal_year, "period": self.period,
            "start_date": getattr(self,"start_date",None), "end_date": getattr(self,"end_date",None),
            "fund_id": getattr(self,"fund_id",None), "branch_id": getattr(self,"branch_id",None),
            "status": self.status, "currency": self.currency,
            "line_items": self.line_items,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }
        return {k:v for k,v in doc.items() if v is not None}

    @classmethod
    def _normalise(cls, doc):
        if not doc: return None
        for f in ["_id","business_id","fund_id","branch_id"]:
            if doc.get(f): doc[f] = str(doc[f])
        for f in cls.FIELDS_TO_DECRYPT:
            if f in doc:
                try: doc[f] = decrypt_data(doc[f])
                except: pass
        doc.pop("hashed_name", None)
        return doc

    @classmethod
    def get_by_id(cls, budget_id, business_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"_id": ObjectId(budget_id)}
            if business_id: q["business_id"] = ObjectId(business_id)
            return cls._normalise(c.find_one(q))
        except: return None

    @classmethod
    def get_all(cls, business_id, fiscal_year=None, fund_id=None, page=1, per_page=20):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id)}
            if fiscal_year: q["fiscal_year"] = fiscal_year
            if fund_id: q["fund_id"] = ObjectId(fund_id)
            total = c.count_documents(q)
            cursor = c.find(q).sort("fiscal_year", -1).skip((page-1)*per_page).limit(per_page)
            return {"budgets": [cls._normalise(d) for d in cursor], "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page, "per_page": per_page}
        except: return {"budgets": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_with_actuals(cls, budget_id, business_id):
        """Get budget with actual spend per line item."""
        try:
            budget = cls.get_by_id(budget_id, business_id)
            if not budget: return None

            start = budget.get("start_date") or f"{budget['fiscal_year']}-01-01"
            end = budget.get("end_date") or f"{budget['fiscal_year']}-12-31"

            txn_coll = db.get_collection(Transaction.collection_name)

            total_budgeted_income = 0; total_budgeted_expense = 0
            total_actual_income = 0; total_actual_expense = 0

            for item in budget.get("line_items", []):
                cat_id = item.get("category_id")
                budgeted = item.get("budgeted_amount", 0)
                item_type = item.get("type", "Expense")

                # Get actual from transactions
                match_q = {
                    "business_id": ObjectId(business_id),
                    "transaction_date": {"$gte": start, "$lte": end},
                    "hashed_status": {"$ne": hash_data("Voided")},
                }
                if cat_id: match_q["category_id"] = ObjectId(cat_id)
                if budget.get("fund_id"): match_q["fund_id"] = ObjectId(budget["fund_id"])
                match_q["hashed_transaction_type"] = hash_data(item_type)

                pipeline = [{"$match": match_q}, {"$group": {"_id": None, "actual": {"$sum": "$amount"}}}]
                agg = list(txn_coll.aggregate(pipeline))
                actual = agg[0]["actual"] if agg else 0

                item["actual_amount"] = round(actual, 2)
                item["variance"] = round(budgeted - actual, 2)
                item["utilisation_pct"] = round((actual / budgeted * 100), 1) if budgeted > 0 else 0

                if item_type == "Income":
                    total_budgeted_income += budgeted; total_actual_income += actual
                else:
                    total_budgeted_expense += budgeted; total_actual_expense += actual

            budget["totals"] = {
                "budgeted_income": round(total_budgeted_income, 2),
                "actual_income": round(total_actual_income, 2),
                "budgeted_expense": round(total_budgeted_expense, 2),
                "actual_expense": round(total_actual_expense, 2),
                "budgeted_net": round(total_budgeted_income - total_budgeted_expense, 2),
                "actual_net": round(total_actual_income - total_actual_expense, 2),
            }

            return budget
        except Exception as e: Log.error(f"[Budget.get_with_actuals] {e}"); return None

    @classmethod
    def update(cls, budget_id, business_id, **updates):
        updates["updated_at"] = datetime.utcnow()
        updates = {k:v for k,v in updates.items() if v is not None}
        if "name" in updates and updates["name"]:
            p = updates["name"]; updates["name"] = encrypt_data(p); updates["hashed_name"] = hash_data(p.strip().lower())
        if "description" in updates and updates["description"]: updates["description"] = encrypt_data(updates["description"])
        for oid in ["fund_id","branch_id"]:
            if oid in updates and updates[oid]: updates[oid] = ObjectId(updates[oid])
        return super().update(budget_id, business_id, **updates)

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("fiscal_year", -1)])
            c.create_index([("business_id", 1), ("fund_id", 1)])
            return True
        except: return False


# ═══════════════════════════════════════════════════════════════
# BANK RECONCILIATION
# ═══════════════════════════════════════════════════════════════

class Reconciliation(BaseModel):
    """Bank reconciliation record."""
    collection_name = "reconciliations"

    STATUS_IN_PROGRESS = "In Progress"
    STATUS_COMPLETED = "Completed"
    STATUSES = [STATUS_IN_PROGRESS, STATUS_COMPLETED]

    def __init__(self, account_id, statement_date, statement_ending_balance,
                 status="In Progress", reconciled_transactions=None,
                 adjustments=None, notes=None,
                 user_id=None, user__id=None, business_id=None, **kw):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kw)
        self.business_id = ObjectId(business_id) if business_id else None
        self.account_id = ObjectId(account_id) if account_id else None
        self.statement_date = statement_date
        self.statement_ending_balance = float(statement_ending_balance)
        self.status = status
        self.reconciled_transactions = reconciled_transactions or []  # list of txn_ids
        self.unreconciled_transactions = []
        if adjustments: self.adjustments = adjustments
        if notes: self.notes = notes
        self.difference = 0.0
        self.created_at = datetime.utcnow(); self.updated_at = datetime.utcnow()

    def to_dict(self):
        doc = {
            "business_id": self.business_id, "account_id": self.account_id,
            "statement_date": self.statement_date,
            "statement_ending_balance": self.statement_ending_balance,
            "status": self.status,
            "reconciled_transactions": self.reconciled_transactions,
            "unreconciled_transactions": getattr(self,"unreconciled_transactions",None),
            "adjustments": getattr(self,"adjustments",None),
            "notes": getattr(self,"notes",None),
            "difference": self.difference,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }
        return {k:v for k,v in doc.items() if v is not None}

    @classmethod
    def _normalise(cls, doc):
        if not doc: return None
        for f in ["_id","business_id","account_id"]: 
            if doc.get(f): doc[f] = str(doc[f])
        return doc

    @classmethod
    def get_by_id(cls, recon_id, business_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"_id": ObjectId(recon_id)}
            if business_id: q["business_id"] = ObjectId(business_id)
            return cls._normalise(c.find_one(q))
        except: return None

    @classmethod
    def calculate_difference(cls, recon_id, business_id):
        """Calculate difference between statement balance and reconciled transactions."""
        try:
            recon = cls.get_by_id(recon_id, business_id)
            if not recon: return None

            account = Account.get_by_id(recon["account_id"], business_id)
            if not account: return None

            # Sum reconciled transactions
            txn_coll = db.get_collection(Transaction.collection_name)
            rec_ids = [ObjectId(t) for t in recon.get("reconciled_transactions", [])]

            if rec_ids:
                pipeline = [
                    {"$match": {"_id": {"$in": rec_ids}}},
                    {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
                ]
                agg = list(txn_coll.aggregate(pipeline))
                reconciled_total = agg[0]["total"] if agg else 0
            else:
                reconciled_total = 0

            stmt_balance = recon.get("statement_ending_balance", 0)
            difference = round(stmt_balance - reconciled_total, 2)

            # Update
            c = db.get_collection(cls.collection_name)
            c.update_one(
                {"_id": ObjectId(recon_id), "business_id": ObjectId(business_id)},
                {"$set": {"difference": difference, "updated_at": datetime.utcnow()}},
            )

            return {"statement_balance": stmt_balance, "reconciled_total": round(reconciled_total, 2), "difference": difference}
        except Exception as e: Log.error(f"[Reconciliation.calculate] {e}"); return None

    @classmethod
    def complete(cls, recon_id, business_id):
        """Mark reconciliation as completed and mark transactions as reconciled."""
        try:
            recon = cls.get_by_id(recon_id, business_id)
            if not recon: return False

            # Mark transactions as reconciled
            txn_coll = db.get_collection(Transaction.collection_name)
            rec_ids = [ObjectId(t) for t in recon.get("reconciled_transactions", [])]
            if rec_ids:
                txn_coll.update_many(
                    {"_id": {"$in": rec_ids}},
                    {"$set": {"status": "Reconciled", "hashed_status": hash_data("Reconciled"), "updated_at": datetime.utcnow()}},
                )

            c = db.get_collection(cls.collection_name)
            c.update_one(
                {"_id": ObjectId(recon_id), "business_id": ObjectId(business_id)},
                {"$set": {"status": cls.STATUS_COMPLETED, "updated_at": datetime.utcnow()}},
            )
            return True
        except Exception as e: Log.error(f"[Reconciliation.complete] {e}"); return False

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("account_id", 1), ("statement_date", -1)])
            return True
        except: return False


# ═══════════════════════════════════════════════════════════════
# PAYMENT VOUCHER
# ═══════════════════════════════════════════════════════════════

class PaymentVoucher(BaseModel):
    """Payment voucher / cheque printing record."""
    collection_name = "payment_vouchers"

    STATUS_DRAFT = "Draft"
    STATUS_APPROVED = "Approved"
    STATUS_PAID = "Paid"
    STATUS_CANCELLED = "Cancelled"
    STATUSES = [STATUS_DRAFT, STATUS_APPROVED, STATUS_PAID, STATUS_CANCELLED]

    def __init__(self, voucher_number, payee_id, amount, payment_date,
                 description=None, fund_id=None, account_id=None, category_id=None,
                 payment_method="Cheque", cheque_number=None, memo=None,
                 status="Draft", currency="GBP",
                 approved_by=None, branch_id=None,
                 user_id=None, user__id=None, business_id=None, **kw):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kw)
        self.business_id = ObjectId(business_id) if business_id else None

        self.voucher_number = voucher_number
        self.payee_id = ObjectId(payee_id) if payee_id else None
        self.amount = round(float(amount), 2)
        self.payment_date = payment_date
        if description: self.description = encrypt_data(description)
        if fund_id: self.fund_id = ObjectId(fund_id)
        if account_id: self.account_id = ObjectId(account_id)
        if category_id: self.category_id = ObjectId(category_id)
        self.payment_method = payment_method
        if cheque_number: self.cheque_number = cheque_number
        if memo: self.memo = encrypt_data(memo)
        self.status = status
        self.currency = currency
        if approved_by: self.approved_by = ObjectId(approved_by)
        if branch_id: self.branch_id = ObjectId(branch_id)

        # For cheque printing
        self.cheque_data = None  # populated on get

        self.created_at = datetime.utcnow(); self.updated_at = datetime.utcnow()

    def to_dict(self):
        doc = {
            "business_id": self.business_id,
            "voucher_number": self.voucher_number,
            "payee_id": self.payee_id, "amount": self.amount,
            "payment_date": self.payment_date,
            "description": getattr(self,"description",None),
            "fund_id": getattr(self,"fund_id",None),
            "account_id": getattr(self,"account_id",None),
            "category_id": getattr(self,"category_id",None),
            "payment_method": self.payment_method,
            "cheque_number": getattr(self,"cheque_number",None),
            "memo": getattr(self,"memo",None),
            "status": self.status, "currency": self.currency,
            "approved_by": getattr(self,"approved_by",None),
            "branch_id": getattr(self,"branch_id",None),
            "created_at": self.created_at, "updated_at": self.updated_at,
        }
        return {k:v for k,v in doc.items() if v is not None}

    @classmethod
    def _normalise(cls, doc):
        if not doc: return None
        for f in ["_id","business_id","payee_id","fund_id","account_id","category_id","approved_by","branch_id"]:
            if doc.get(f): doc[f] = str(doc[f])
        for f in ["description","memo"]:
            if f in doc and isinstance(doc[f], str):
                try: doc[f] = decrypt_data(doc[f])
                except: pass
        return doc

    @classmethod
    def get_by_id(cls, voucher_id, business_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"_id": ObjectId(voucher_id)}
            if business_id: q["business_id"] = ObjectId(business_id)
            doc = cls._normalise(c.find_one(q))
            if doc and doc.get("payee_id"):
                payee = Payee.get_by_id(doc["payee_id"], business_id)
                if payee:
                    doc["cheque_data"] = {
                        "payee_name": payee.get("name"),
                        "amount": doc.get("amount"),
                        "currency": doc.get("currency"),
                        "date": doc.get("payment_date"),
                        "memo": doc.get("memo") or doc.get("description"),
                        "cheque_number": doc.get("cheque_number"),
                        "voucher_number": doc.get("voucher_number"),
                    }
            return doc
        except Exception as e: Log.error(f"[PaymentVoucher.get_by_id] {e}"); return None

    @classmethod
    def get_all(cls, business_id, status=None, payee_id=None, start_date=None, end_date=None, page=1, per_page=50):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id)}
            if status: q["status"] = status
            if payee_id: q["payee_id"] = ObjectId(payee_id)
            if start_date: q.setdefault("payment_date",{})["$gte"] = start_date
            if end_date: q.setdefault("payment_date",{})["$lte"] = end_date

            total = c.count_documents(q)
            cursor = c.find(q).sort("payment_date", -1).skip((page-1)*per_page).limit(per_page)
            return {"vouchers": [cls._normalise(d) for d in cursor], "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page, "per_page": per_page}
        except: return {"vouchers": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def approve(cls, voucher_id, business_id, approved_by):
        try:
            c = db.get_collection(cls.collection_name)
            result = c.update_one(
                {"_id": ObjectId(voucher_id), "business_id": ObjectId(business_id), "status": cls.STATUS_DRAFT},
                {"$set": {"status": cls.STATUS_APPROVED, "approved_by": ObjectId(approved_by), "updated_at": datetime.utcnow()}},
            )
            return result.modified_count > 0
        except: return False

    @classmethod
    def mark_paid(cls, voucher_id, business_id, transaction_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            update = {"status": cls.STATUS_PAID, "updated_at": datetime.utcnow()}
            if transaction_id: update["transaction_id"] = ObjectId(transaction_id)
            result = c.update_one(
                {"_id": ObjectId(voucher_id), "business_id": ObjectId(business_id), "status": cls.STATUS_APPROVED},
                {"$set": update},
            )
            return result.modified_count > 0
        except: return False

    @classmethod
    def get_next_voucher_number(cls, business_id):
        try:
            c = db.get_collection(cls.collection_name)
            last = c.find_one({"business_id": ObjectId(business_id)}, sort=[("created_at", -1)])
            if last and last.get("voucher_number"):
                try:
                    num = int(last["voucher_number"].replace("PV-",""))
                    return f"PV-{num+1:06d}"
                except: pass
            return "PV-000001"
        except: return "PV-000001"

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("voucher_number", 1)], unique=True)
            c.create_index([("business_id", 1), ("status", 1)])
            c.create_index([("business_id", 1), ("payee_id", 1)])
            c.create_index([("business_id", 1), ("payment_date", -1)])
            return True
        except: return False


# ═══════════════════════════════════════════════════════════════
# BANK IMPORT RULE (auto-categorisation)
# ═══════════════════════════════════════════════════════════════

class BankImportRule(BaseModel):
    """Auto-categorisation rule for bank-imported transactions."""
    collection_name = "bank_import_rules"

    def __init__(self, match_text, account_id=None, category_id=None, fund_id=None,
                 payee_id=None, transaction_type="Expense", is_active=True,
                 user_id=None, user__id=None, business_id=None, **kw):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kw)
        self.business_id = ObjectId(business_id) if business_id else None
        self.match_text = match_text.strip().lower()
        if account_id: self.account_id = ObjectId(account_id)
        if category_id: self.category_id = ObjectId(category_id)
        if fund_id: self.fund_id = ObjectId(fund_id)
        if payee_id: self.payee_id = ObjectId(payee_id)
        self.transaction_type = transaction_type
        self.is_active = bool(is_active)
        self.created_at = datetime.utcnow(); self.updated_at = datetime.utcnow()

    def to_dict(self):
        doc = {"business_id": self.business_id, "match_text": self.match_text,
               "account_id": getattr(self,"account_id",None), "category_id": getattr(self,"category_id",None),
               "fund_id": getattr(self,"fund_id",None), "payee_id": getattr(self,"payee_id",None),
               "transaction_type": self.transaction_type, "is_active": self.is_active,
               "created_at": self.created_at, "updated_at": self.updated_at}
        return {k:v for k,v in doc.items() if v is not None}

    @classmethod
    def _normalise(cls, doc):
        if not doc: return None
        for f in ["_id","business_id","account_id","category_id","fund_id","payee_id"]:
            if doc.get(f): doc[f] = str(doc[f])
        return doc

    @classmethod
    def get_all(cls, business_id):
        try:
            c = db.get_collection(cls.collection_name)
            cursor = c.find({"business_id": ObjectId(business_id), "is_active": True})
            return [cls._normalise(d) for d in cursor]
        except: return []

    @classmethod
    def match_transaction(cls, business_id, description):
        """Find a matching rule for a bank transaction description."""
        try:
            rules = cls.get_all(business_id)
            desc_lower = description.strip().lower()
            for rule in rules:
                if rule.get("match_text") in desc_lower:
                    return rule
            return None
        except: return None

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("match_text", 1)])
            return True
        except: return False
