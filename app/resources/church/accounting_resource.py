# resources/church/accounting_resource.py

import time
from datetime import datetime
from bson import ObjectId
from flask import g, request
from flask.views import MethodView
from flask_smorest import Blueprint
from pymongo.errors import PyMongoError
from ...utils.crypt import hash_data

from ...extensions.db import db
from ...utils.helpers import stringify_object_ids

from ..doseal.admin.admin_business_resource import token_required

from ...models.church.accounting_model import (
    Account, Fund, Category, Payee, Transaction,
    Budget, Reconciliation, PaymentVoucher, BankImportRule,
)
from ...models.church.branch_model import Branch

from ...schemas.church.accounting_schema import (
    AccountCreateSchema, AccountUpdateSchema, AccountIdQuerySchema, AccountListQuerySchema,
    FundCreateSchema, FundUpdateSchema, FundIdQuerySchema, FundListQuerySchema,
    CategoryCreateSchema, CategoryUpdateSchema, CategoryIdQuerySchema, CategoryListQuerySchema,
    PayeeCreateSchema, PayeeUpdateSchema, PayeeIdQuerySchema, PayeeListQuerySchema,
    TransactionCreateSchema, TransactionUpdateSchema, TransactionIdQuerySchema, TransactionListQuerySchema, TransactionVoidSchema,
    IncomeExpenseReportQuerySchema, BalanceSheetQuerySchema, FundSummaryReportQuerySchema,
    BudgetCreateSchema, BudgetUpdateSchema, BudgetIdQuerySchema, BudgetListQuerySchema,
    ReconciliationCreateSchema, ReconciliationUpdateSchema, ReconciliationIdQuerySchema, ReconciliationCompleteSchema,
    VoucherCreateSchema, VoucherIdQuerySchema, VoucherListQuerySchema, VoucherApproveSchema, VoucherMarkPaidSchema,
    BankImportRuleCreateSchema, BankImportRuleIdQuerySchema, BankImportSchema,
    FinancialDashboardQuerySchema,
)
from ...utils.json_response import prepared_response
from ...utils.helpers import make_log_tag, _resolve_business_id
from ...utils.logger import Log

blp_accounting = Blueprint("accounting", __name__, description="Church accounting and financial management")


# ════════════════════════════ ACCOUNTS ════════════════════════════

@blp_accounting.route("/accounting/account", methods=["POST","GET","PATCH","DELETE"])
class AccountResource(MethodView):
    @token_required
    @blp_accounting.arguments(AccountCreateSchema, location="json")
    @blp_accounting.response(201)
    @blp_accounting.doc(summary="Create a chart of accounts entry", security=[{"Bearer":[]}])
    def post(self, json_data):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui, json_data.get("business_id"))
        json_data["business_id"]=bid; json_data["user_id"]=ui.get("user_id"); json_data["user__id"]=str(ui.get("_id"))
        try:
            a = Account(**json_data); aid = a.save()
            if not aid: return prepared_response(False,"BAD_REQUEST","Failed to create account.")
            return prepared_response(True,"CREATED","Account created.",data=Account.get_by_id(aid,bid))
        except Exception as e: return prepared_response(False,"INTERNAL_SERVER_ERROR","Error.",errors=[str(e)])

    
    @token_required
    @blp_accounting.arguments(AccountIdQuerySchema, location="query")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Get a single account with balance", security=[{"Bearer":[]}])
    def get(self, qd):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui)
        a = Account.get_by_id(qd.get("account_id"), bid)
        if not a: return prepared_response(False,"NOT_FOUND","Account not found.")
        a["children"] = Account.get_children(bid, qd.get("account_id"))
        return prepared_response(True,"OK","Account retrieved.",data=a)

    @token_required
    @blp_accounting.arguments(AccountUpdateSchema, location="json")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Update an account", security=[{"Bearer":[]}])
    def patch(self, d):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui); aid = d.pop("account_id",None)
        if not Account.get_by_id(aid, bid): return prepared_response(False,"NOT_FOUND","Account not found.")
        Account.update(aid, bid, **d)
        return prepared_response(True,"OK","Account updated.",data=Account.get_by_id(aid,bid))

    @token_required
    @blp_accounting.arguments(AccountIdQuerySchema, location="query")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Delete an account", security=[{"Bearer":[]}])
    def delete(self, qd):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui)
        if not Account.get_by_id(qd.get("account_id"), bid): return prepared_response(False,"NOT_FOUND","Account not found.")
        Account.delete(qd["account_id"], bid)
        return prepared_response(True,"OK","Account deleted.")

@blp_accounting.route("/accounting/accounts", methods=["GET"])
class AccountListResource(MethodView):
    @token_required
    @blp_accounting.arguments(AccountListQuerySchema, location="query")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="List chart of accounts", security=[{"Bearer":[]}])
    def get(self, qd):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui, qd.get("business_id"))
        r = Account.get_all(bid, account_type=qd.get("account_type"), fund_id=qd.get("fund_id"), page=qd.get("page",1), per_page=qd.get("per_page",100))
        if not r.get("accounts"): return prepared_response(False,"NOT_FOUND","No accounts found.")
        return prepared_response(True,"OK","Accounts retrieved.",data=r)


# ════════════════════════════ FUNDS ════════════════════════════

@blp_accounting.route("/accounting/fund", methods=["POST","GET","PATCH","DELETE"])
class FundResource(MethodView):
    @token_required
    @blp_accounting.arguments(FundCreateSchema, location="json")
    @blp_accounting.response(201)
    @blp_accounting.doc(summary="Create a fund", security=[{"Bearer":[]}])
    def post(self, json_data):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui, json_data.get("business_id"))
        json_data["business_id"]=bid; json_data["user_id"]=ui.get("user_id"); json_data["user__id"]=str(ui.get("_id"))
        f = Fund(**json_data); fid = f.save()
        if not fid: return prepared_response(False,"BAD_REQUEST","Failed to create fund.")
        return prepared_response(True,"CREATED","Fund created.",data=Fund.get_by_id(fid,bid))

    @token_required
    @blp_accounting.arguments(FundIdQuerySchema, location="query")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Get a fund with balance and progress", security=[{"Bearer":[]}])
    def get(self, qd):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui)
        f = Fund.get_by_id(qd.get("fund_id"), bid)
        if not f: return prepared_response(False,"NOT_FOUND","Fund not found.")
        return prepared_response(True,"OK","Fund retrieved.",data=f)

    @token_required
    @blp_accounting.arguments(FundUpdateSchema, location="json")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Update a fund", security=[{"Bearer":[]}])
    def patch(self, d):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui); fid = d.pop("fund_id",None)
        if not Fund.get_by_id(fid, bid): return prepared_response(False,"NOT_FOUND","Fund not found.")
        Fund.update(fid, bid, **d)
        return prepared_response(True,"OK","Fund updated.",data=Fund.get_by_id(fid,bid))

    @token_required
    @blp_accounting.arguments(FundIdQuerySchema, location="query")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Delete a fund", security=[{"Bearer":[]}])
    def delete(self, qd):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui)
        Fund.delete(qd["fund_id"], bid)
        return prepared_response(True,"OK","Fund deleted.")

@blp_accounting.route("/accounting/funds", methods=["GET"])
class FundListResource(MethodView):
    @token_required
    @blp_accounting.arguments(FundListQuerySchema, location="query")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="List all funds with balances", security=[{"Bearer":[]}])
    def get(self, qd):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui, qd.get("business_id"))
        r = Fund.get_all(bid, page=qd.get("page",1), per_page=qd.get("per_page",50))
        return prepared_response(True,"OK","Funds retrieved.",data=r)

@blp_accounting.route("/accounting/funds/summary", methods=["GET"])
class FundSummaryResource(MethodView):
    @token_required
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Fund summary with total balance across all funds", security=[{"Bearer":[]}])
    def get(self):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui, request.args.get("business_id"))
        return prepared_response(True,"OK","Fund summary.",data=Fund.get_summary(bid))


# ════════════════════════════ CATEGORIES ════════════════════════════

@blp_accounting.route("/accounting/category", methods=["POST","GET","PATCH","DELETE"])
class CategoryResource(MethodView):
    @token_required
    @blp_accounting.arguments(CategoryCreateSchema, location="json")
    @blp_accounting.response(201)
    @blp_accounting.doc(summary="Create a transaction category", security=[{"Bearer":[]}])
    def post(self, json_data):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui)
        json_data["business_id"]=bid; json_data["user_id"]=ui.get("user_id"); json_data["user__id"]=str(ui.get("_id"))
        cat = Category(**json_data); cid = cat.save()
        if not cid: return prepared_response(False,"BAD_REQUEST","Failed.")
        return prepared_response(True,"CREATED","Category created.",data=Category.get_by_id(cid,bid))

    @token_required
    @blp_accounting.arguments(CategoryIdQuerySchema, location="query")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Get a category", security=[{"Bearer":[]}])
    def get(self, qd):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui)
        c = Category.get_by_id(qd.get("category_id"), bid)
        if not c: return prepared_response(False,"NOT_FOUND","Category not found.")
        return prepared_response(True,"OK","Category retrieved.",data=c)

    @token_required
    @blp_accounting.arguments(CategoryUpdateSchema, location="json")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Update a category", security=[{"Bearer":[]}])
    def patch(self, d):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui); cid = d.pop("category_id")
        Category.update(cid, bid, **d)
        return prepared_response(True,"OK","Updated.",data=Category.get_by_id(cid,bid))

    @token_required
    @blp_accounting.arguments(CategoryIdQuerySchema, location="query")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Delete a category", security=[{"Bearer":[]}])
    def delete(self, qd):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui)
        Category.delete(qd["category_id"], bid)
        return prepared_response(True,"OK","Deleted.")

@blp_accounting.route("/accounting/categories", methods=["GET"])
class CategoryListResource(MethodView):
    @token_required
    @blp_accounting.arguments(CategoryListQuerySchema, location="query")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="List categories", security=[{"Bearer":[]}])
    def get(self, qd):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui, qd.get("business_id"))
        return prepared_response(True,"OK","Categories.",data=Category.get_all(bid, category_type=qd.get("category_type"), page=qd.get("page",1), per_page=qd.get("per_page",100)))


# ════════════════════════════ PAYEES ════════════════════════════

@blp_accounting.route("/accounting/payee", methods=["POST","GET","PATCH","DELETE"])
class PayeeResource(MethodView):
    @token_required
    @blp_accounting.arguments(PayeeCreateSchema, location="json")
    @blp_accounting.response(201)
    @blp_accounting.doc(summary="Create a payee/vendor", security=[{"Bearer":[]}])
    def post(self, json_data):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui)
        json_data["business_id"]=bid; json_data["user_id"]=ui.get("user_id"); json_data["user__id"]=str(ui.get("_id"))
        p = Payee(**json_data); pid = p.save()
        if not pid: return prepared_response(False,"BAD_REQUEST","Failed.")
        return prepared_response(True,"CREATED","Payee created.",data=Payee.get_by_id(pid,bid))

    @token_required
    @blp_accounting.arguments(PayeeIdQuerySchema, location="query")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Get a payee", security=[{"Bearer":[]}])
    def get(self, qd):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui)
        p = Payee.get_by_id(qd.get("payee_id"), bid)
        if not p: return prepared_response(False,"NOT_FOUND","Payee not found.")
        return prepared_response(True,"OK","Payee.",data=p)

    @token_required
    @blp_accounting.arguments(PayeeUpdateSchema, location="json")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Update a payee", security=[{"Bearer":[]}])
    def patch(self, d):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui); pid = d.pop("payee_id")
        Payee.update(pid, bid, **d)
        return prepared_response(True,"OK","Updated.",data=Payee.get_by_id(pid,bid))

    @token_required
    @blp_accounting.arguments(PayeeIdQuerySchema, location="query")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Delete a payee", security=[{"Bearer":[]}])
    def delete(self, qd):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))
        target_business_id = _resolve_business_id(user_info, qd.get("business_id"))

        log_tag = make_log_tag(
            "accounting_resource.py", "PayeeResource", "delete",
            client_ip, auth_user__id, account_type,
            auth_business_id, target_business_id,
        )

        payee_id = qd.get("payee_id")

        existing = Payee.get_by_id(payee_id, target_business_id)
        if not existing:
            Log.info(f"{log_tag} payee not found: {payee_id}")
            return prepared_response(False, "NOT_FOUND", "Payee not found.")

        try:
            result = Payee.delete(payee_id, target_business_id)
            if not result:
                return prepared_response(False, "BAD_REQUEST", "Failed to delete payee.")

            Log.info(f"{log_tag} payee deleted: {payee_id}")
            return prepared_response(True, "OK", "Payee deleted.")
        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])

@blp_accounting.route("/accounting/payees", methods=["GET"])
class PayeeListResource(MethodView):
    @token_required
    @blp_accounting.arguments(PayeeListQuerySchema, location="query")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="List payees/vendors", security=[{"Bearer":[]}])
    def get(self, qd):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui, qd.get("business_id"))
        return prepared_response(True,"OK","Payees.",data=Payee.get_all(bid, payee_type=qd.get("payee_type"), page=qd.get("page",1), per_page=qd.get("per_page",100)))


# ════════════════════════════ TRANSACTIONS ════════════════════════════

@blp_accounting.route("/accounting/transaction", methods=["POST","GET","PATCH","DELETE"])
class TransactionResource(MethodView):
    @token_required
    @blp_accounting.arguments(TransactionCreateSchema, location="json")
    @blp_accounting.response(201)
    @blp_accounting.doc(
        summary="Create a financial transaction (income/expense/transfer)",
        description="Auto-adjusts account balances and fund balances. Validates all referenced accounts, funds, categories, and payees.",
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))
        target_business_id = _resolve_business_id(user_info, json_data.get("business_id"))

        log_tag = make_log_tag(
            "accounting_resource.py", "TransactionResource", "post",
            client_ip, auth_user__id, account_type,
            auth_business_id, target_business_id,
        )

        json_data["business_id"] = target_business_id
        json_data["user_id"] = user_info.get("user_id")
        json_data["user__id"] = auth_user__id

        # ── Validate debit account ──
        debit_account_id = json_data.get("debit_account_id")
        if debit_account_id:
            debit_account = Account.get_by_id(debit_account_id, target_business_id)
            if not debit_account:
                Log.info(f"{log_tag} debit account not found: {debit_account_id}")
                return prepared_response(False, "NOT_FOUND", f"Debit account '{debit_account_id}' not found.")

        # ── Validate credit account ──
        credit_account_id = json_data.get("credit_account_id")
        if credit_account_id:
            credit_account = Account.get_by_id(credit_account_id, target_business_id)
            if not credit_account:
                Log.info(f"{log_tag} credit account not found: {credit_account_id}")
                return prepared_response(False, "NOT_FOUND", f"Credit account '{credit_account_id}' not found.")

        # ── Validate fund ──
        fund_id = json_data.get("fund_id")
        if fund_id:
            fund = Fund.get_by_id(fund_id, target_business_id)
            if not fund:
                Log.info(f"{log_tag} fund not found: {fund_id}")
                return prepared_response(False, "NOT_FOUND", f"Fund '{fund_id}' not found.")

        # ── Validate category ──
        category_id = json_data.get("category_id")
        if category_id:
            category = Category.get_by_id(category_id, target_business_id)
            if not category:
                Log.info(f"{log_tag} category not found: {category_id}")
                return prepared_response(False, "NOT_FOUND", f"Category '{category_id}' not found.")

        # ── Validate payee ──
        payee_id = json_data.get("payee_id")
        if payee_id:
            payee = Payee.get_by_id(payee_id, target_business_id)
            if not payee:
                Log.info(f"{log_tag} payee not found: {payee_id}")
                return prepared_response(False, "NOT_FOUND", f"Payee '{payee_id}' not found.")

        # ── Validate branch ──
        branch_id = json_data.get("branch_id")
        if branch_id:
            from ...models.church.branch_model import Branch
            branch = Branch.get_by_id(branch_id, target_business_id)
            if not branch:
                Log.info(f"{log_tag} branch not found: {branch_id}")
                return prepared_response(False, "NOT_FOUND", f"Branch '{branch_id}' not found.")

        # ── Create transaction ──
        try:
            Log.info(f"{log_tag} creating transaction")
            start_time = time.time()

            txn = Transaction(**json_data)
            tid = txn.save()

            duration = time.time() - start_time
            Log.info(f"{log_tag} transaction.save() returned {tid} in {duration:.2f}s")

            if not tid:
                return prepared_response(False, "BAD_REQUEST", "Failed to create transaction.")

            amount = json_data.get("amount", 0)
            tt = json_data.get("transaction_type")

            # ── Adjust account balances ──
            if debit_account_id:
                Account.adjust_balance(debit_account_id, target_business_id, amount if tt == "Expense" else -amount)
            if credit_account_id:
                Account.adjust_balance(credit_account_id, target_business_id, -amount if tt == "Expense" else amount)

            # ── Adjust fund balance ──
            if fund_id:
                fund_adj = amount if tt == "Income" else -amount
                Fund.adjust_balance(fund_id, target_business_id, fund_adj)

            created = Transaction.get_by_id(tid, target_business_id)
            Log.info(f"{log_tag} transaction created: {tid}, type={tt}, amount={amount}")
            return prepared_response(True, "CREATED", "Transaction recorded.", data=created)

        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An unexpected error occurred.", errors=[str(e)])
        except Exception as e:
            Log.error(f"{log_tag} unexpected error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An unexpected error occurred.", errors=[str(e)])
        
    @token_required
    @blp_accounting.arguments(TransactionIdQuerySchema, location="query")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Get a transaction", security=[{"Bearer":[]}])
    def get(self, qd):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui)
        t = Transaction.get_by_id(qd.get("transaction_id"), bid)
        if not t: return prepared_response(False,"NOT_FOUND","Transaction not found.")
        return prepared_response(True,"OK","Transaction.",data=t)

    @token_required
    @blp_accounting.arguments(TransactionUpdateSchema, location="json")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Update a transaction (description, memo, category, fund, status)", security=[{"Bearer":[]}])
    def patch(self, d):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui); tid = d.pop("transaction_id")
        existing = Transaction.get_by_id(tid, bid)
        if not existing: return prepared_response(False,"NOT_FOUND","Transaction not found.")
        if existing.get("status") == "Voided": return prepared_response(False,"CONFLICT","Cannot edit a voided transaction.")
        Transaction.update(tid, bid, **d)
        return prepared_response(True,"OK","Updated.",data=Transaction.get_by_id(tid,bid))

    @token_required
    @blp_accounting.arguments(TransactionIdQuerySchema, location="query")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Delete a transaction (only pending)", security=[{"Bearer":[]}])
    def delete(self, qd):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui)
        t = Transaction.get_by_id(qd.get("transaction_id"), bid)
        if not t: return prepared_response(False,"NOT_FOUND","Not found.")
        if t.get("status") not in ("Pending",): return prepared_response(False,"CONFLICT","Only pending transactions can be deleted.")
        Transaction.delete(qd["transaction_id"], bid)
        return prepared_response(True,"OK","Deleted.")

@blp_accounting.route("/accounting/transactions", methods=["GET"])
class TransactionListResource(MethodView):
    @token_required
    @blp_accounting.arguments(TransactionListQuerySchema, location="query")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="List transactions with filters", security=[{"Bearer":[]}])
    def get(self, qd):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui, qd.get("business_id"))
        r = Transaction.get_all(bid, page=qd.get("page",1), per_page=qd.get("per_page",50),
            transaction_type=qd.get("transaction_type"), status=qd.get("status"),
            fund_id=qd.get("fund_id"), account_id=qd.get("account_id"),
            category_id=qd.get("category_id"), payee_id=qd.get("payee_id"),
            start_date=qd.get("start_date"), end_date=qd.get("end_date"), branch_id=qd.get("branch_id"))
        if not r.get("transactions"): return prepared_response(False,"NOT_FOUND","No transactions.")
        return prepared_response(True,"OK","Transactions.",data=r)

@blp_accounting.route("/accounting/transaction/void", methods=["POST"])
class TransactionVoidResource(MethodView):
    @token_required
    @blp_accounting.arguments(TransactionVoidSchema, location="json")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Void a transaction (reverses account/fund balances)", security=[{"Bearer":[]}])
    def post(self, d):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui)
        ok = Transaction.void(d.get("transaction_id"), bid)
        if ok: return prepared_response(True,"OK","Transaction voided. Balances reversed.")
        return prepared_response(False,"BAD_REQUEST","Failed to void.")


# ════════════════════════════ REPORTS ════════════════════════════

@blp_accounting.route("/accounting/reports/income-expense", methods=["GET"])
class IncomeExpenseReportResource(MethodView):
    @token_required
    @blp_accounting.arguments(IncomeExpenseReportQuerySchema, location="query")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Income & Expense statement for a period", security=[{"Bearer":[]}])
    def get(self, qd):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui, qd.get("business_id"))
        r = Transaction.get_income_expense_statement(bid, qd["start_date"], qd["end_date"], fund_id=qd.get("fund_id"), branch_id=qd.get("branch_id"))
        return prepared_response(True,"OK","Income & Expense statement.",data=r)

@blp_accounting.route("/accounting/reports/balance-sheet", methods=["GET"])
class BalanceSheetResource(MethodView):
    @token_required
    @blp_accounting.arguments(BalanceSheetQuerySchema, location="query")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Balance sheet as of a specific date", security=[{"Bearer":[]}])
    def get(self, qd):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui, qd.get("business_id"))
        r = Transaction.get_balance_sheet(bid, qd["as_of_date"], branch_id=qd.get("branch_id"))
        return prepared_response(True,"OK","Balance sheet.",data=r)

@blp_accounting.route("/accounting/reports/fund-summary", methods=["GET"])
class FundSummaryReportResource(MethodView):
    @token_required
    @blp_accounting.arguments(FundSummaryReportQuerySchema, location="query")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Fund summary report (income/expense per fund)", security=[{"Bearer":[]}])
    def get(self, qd):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui, qd.get("business_id"))
        r = Transaction.get_fund_summary(bid, start_date=qd.get("start_date"), end_date=qd.get("end_date"))
        return prepared_response(True,"OK","Fund summary.",data=r)


# ════════════════════════════ BUDGETS ════════════════════════════

@blp_accounting.route("/accounting/budget", methods=["POST","GET","PATCH","DELETE"])
class BudgetResource(MethodView):
    
    @token_required
    @blp_accounting.arguments(BudgetCreateSchema, location="json")
    @blp_accounting.response(201)
    @blp_accounting.doc(
        summary="Create a budget with line items",
        description="Validates fund, branch, and all category IDs in line items before creation.",
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))
        target_business_id = _resolve_business_id(user_info, json_data.get("business_id"))

        log_tag = make_log_tag(
            "accounting_resource.py", "BudgetResource", "post",
            client_ip, auth_user__id, account_type,
            auth_business_id, target_business_id,
        )

        # ── Validate fund ──
        fund_id = json_data.get("fund_id")
        if fund_id:
            fund = Fund.get_by_id(fund_id, target_business_id)
            if not fund:
                Log.info(f"{log_tag} fund not found: {fund_id}")
                return prepared_response(False, "NOT_FOUND", f"Fund '{fund_id}' not found.")

        # ── Validate branch ──
        branch_id = json_data.get("branch_id")
        if branch_id:
            branch = Branch.get_by_id(branch_id, target_business_id)
            if not branch:
                Log.info(f"{log_tag} branch not found: {branch_id}")
                return prepared_response(False, "NOT_FOUND", f"Branch '{branch_id}' not found.")

        # ── Validate category IDs in line items ──
        line_items = json_data.get("line_items") or []
        for idx, item in enumerate(line_items):
            cat_id = item.get("category_id")
            if cat_id:
                category = Category.get_by_id(cat_id, target_business_id)
                if not category:
                    Log.info(f"{log_tag} line item {idx + 1}: category not found: {cat_id}")
                    return prepared_response(
                        False, "NOT_FOUND",
                        f"Line item {idx + 1} ('{item.get('category_name', '')}'): category '{cat_id}' not found.",
                    )

        # ── Create budget ──
        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id

            Log.info(f"{log_tag} creating budget with {len(line_items)} line items")
            start_time = time.time()

            budget = Budget(**json_data)
            budget_id = budget.save()

            duration = time.time() - start_time
            Log.info(f"{log_tag} budget.save() returned {budget_id} in {duration:.2f}s")

            if not budget_id:
                return prepared_response(False, "BAD_REQUEST", "Failed to create budget.")

            created = Budget.get_by_id(budget_id, target_business_id)
            return prepared_response(True, "CREATED", "Budget created.", data=created)

        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An unexpected error occurred.", errors=[str(e)])
        except Exception as e:
            Log.error(f"{log_tag} unexpected error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An unexpected error occurred.", errors=[str(e)])
        
    @token_required
    @blp_accounting.arguments(BudgetIdQuerySchema, location="query")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Get a budget with actual vs budgeted", security=[{"Bearer":[]}])
    def get(self, qd):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui)
        b = Budget.get_with_actuals(qd.get("budget_id"), bid)
        if not b: return prepared_response(False,"NOT_FOUND","Budget not found.")
        return prepared_response(True,"OK","Budget with actuals.",data=b)

    @token_required
    @blp_accounting.arguments(BudgetUpdateSchema, location="json")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Update a budget", security=[{"Bearer":[]}])
    def patch(self, d):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui); buid = d.pop("budget_id")
        Budget.update(buid, bid, **d)
        return prepared_response(True,"OK","Updated.",data=Budget.get_by_id(buid,bid))

    @token_required
    @blp_accounting.arguments(BudgetIdQuerySchema, location="query")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Delete a budget", security=[{"Bearer":[]}])
    def delete(self, qd):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui)
        Budget.delete(qd["budget_id"], bid)
        return prepared_response(True,"OK","Deleted.")

@blp_accounting.route("/accounting/budgets", methods=["GET"])
class BudgetListResource(MethodView):
    @token_required
    @blp_accounting.arguments(BudgetListQuerySchema, location="query")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="List budgets", security=[{"Bearer":[]}])
    def get(self, qd):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui, qd.get("business_id"))
        return prepared_response(True,"OK","Budgets.",data=Budget.get_all(bid, fiscal_year=qd.get("fiscal_year"), fund_id=qd.get("fund_id"), page=qd.get("page",1), per_page=qd.get("per_page",20)))


# ════════════════════════════ RECONCILIATION ════════════════════════════

@blp_accounting.route("/accounting/reconciliation", methods=["POST","GET","PATCH"])
class ReconciliationResource(MethodView):
    
    @token_required
    @blp_accounting.arguments(ReconciliationCreateSchema, location="json")
    @blp_accounting.response(201)
    @blp_accounting.doc(summary="Start a bank reconciliation", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        acc = Account.get_by_id(json_data.get("account_id"), target_business_id)
        if not acc:
            return prepared_response(False, "NOT_FOUND", "Account not found.")

        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = str(user_info.get("_id"))

            r = Reconciliation(**json_data)
            rid = r.save()

            if not rid:
                return prepared_response(False, "BAD_REQUEST", "Failed to start reconciliation.")

            created = Reconciliation.get_by_id(rid, target_business_id)
            return prepared_response(True, "CREATED", "Reconciliation started.", data=created)
        except Exception as e:
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])
    
    @token_required
    @blp_accounting.arguments(ReconciliationIdQuerySchema, location="query")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Get reconciliation with difference", security=[{"Bearer":[]}])
    def get(self, qd):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui)
        r = Reconciliation.get_by_id(qd.get("reconciliation_id"), bid)
        if not r: return prepared_response(False,"NOT_FOUND","Not found.")
        diff = Reconciliation.calculate_difference(qd["reconciliation_id"], bid)
        r = stringify_object_ids(r)
        r["calculation"] = diff
        return prepared_response(True,"OK","Reconciliation.",data=r)

    @token_required
    @blp_accounting.arguments(ReconciliationUpdateSchema, location="json")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Update reconciled transactions list", security=[{"Bearer":[]}])
    def patch(self, d):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui); rid = d.pop("reconciliation_id")
        from bson import ObjectId as BO
        c = db.get_collection(Reconciliation.collection_name)
        update = {"updated_at": datetime.utcnow()}
        if d.get("reconciled_transactions"): update["reconciled_transactions"] = [BO(t) for t in d["reconciled_transactions"]]
        if d.get("notes"): update["notes"] = d["notes"]
        c.update_one({"_id": BO(rid), "business_id": BO(bid)}, {"$set": update})
        r = Reconciliation.get_by_id(rid, bid)
        r = stringify_object_ids(r)
        r["calculation"] = Reconciliation.calculate_difference(rid, bid)
        return prepared_response(True,"OK","Updated.",data=r)

@blp_accounting.route("/accounting/reconciliation/complete", methods=["POST"])
class ReconciliationCompleteResource(MethodView):
    @token_required
    @blp_accounting.arguments(ReconciliationCompleteSchema, location="json")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Complete reconciliation (marks transactions as reconciled)", security=[{"Bearer":[]}])
    def post(self, d):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui)
        ok = Reconciliation.complete(d.get("reconciliation_id"), bid)
        if ok: return prepared_response(True,"OK","Reconciliation completed.")
        return prepared_response(False,"BAD_REQUEST","Failed.")


# ════════════════════════════ PAYMENT VOUCHERS ════════════════════════════

@blp_accounting.route("/accounting/voucher", methods=["POST","GET"])
class VoucherResource(MethodView):
    
    @token_required
    @blp_accounting.arguments(VoucherCreateSchema, location="json")
    @blp_accounting.response(201)
    @blp_accounting.doc(summary="Create a payment voucher (auto-generates voucher number)", security=[{"Bearer": []}])
    def post(self, json_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))
        target_business_id = _resolve_business_id(user_info, json_data.get("business_id"))
        log_tag = make_log_tag("accounting_resource.py", "VoucherCreateResource", "post", client_ip, auth_user__id, account_type, auth_business_id, target_business_id)

        payee_id = json_data.get("payee_id")
        if not Payee.get_by_id(payee_id, target_business_id):
            Log.info(f"{log_tag} payee not found: {payee_id}")
            return prepared_response(False, "NOT_FOUND", f"Payee '{payee_id}' not found.")

        fund_id = json_data.get("fund_id")
        if fund_id:
            if not Fund.get_by_id(fund_id, target_business_id):
                Log.info(f"{log_tag} fund not found: {fund_id}")
                return prepared_response(False, "NOT_FOUND", f"Fund '{fund_id}' not found.")

        account_id = json_data.get("account_id")
        if account_id:
            if not Account.get_by_id(account_id, target_business_id):
                Log.info(f"{log_tag} account not found: {account_id}")
                return prepared_response(False, "NOT_FOUND", f"Account '{account_id}' not found.")

        category_id = json_data.get("category_id")
        if category_id:
            if not Category.get_by_id(category_id, target_business_id):
                Log.info(f"{log_tag} category not found: {category_id}")
                return prepared_response(False, "NOT_FOUND", f"Category '{category_id}' not found.")

        branch_id = json_data.get("branch_id")
        if branch_id:
            if not Branch.get_by_id(branch_id, target_business_id):
                Log.info(f"{log_tag} branch not found: {branch_id}")
                return prepared_response(False, "NOT_FOUND", f"Branch '{branch_id}' not found.")

        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id
            json_data["voucher_number"] = PaymentVoucher.get_next_voucher_number(target_business_id)
            v = PaymentVoucher(**json_data)
            vid = v.save()
            if not vid:
                return prepared_response(False, "BAD_REQUEST", "Failed to create voucher.")
            created = PaymentVoucher.get_by_id(vid, target_business_id)
            Log.info(f"{log_tag} voucher created: {vid}")
            return prepared_response(True, "CREATED", "Voucher created.", data=created)
        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An unexpected error occurred.", errors=[str(e)])
        except Exception as e:
            Log.error(f"{log_tag} unexpected error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An unexpected error occurred.", errors=[str(e)])
    

    @token_required
    @blp_accounting.arguments(VoucherIdQuerySchema, location="query")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Get voucher with cheque printing data", security=[{"Bearer":[]}])
    def get(self, qd):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui)
        v = PaymentVoucher.get_by_id(qd.get("voucher_id"), bid)
        if not v: return prepared_response(False,"NOT_FOUND","Voucher not found.")
        return prepared_response(True,"OK","Voucher.",data=v)

@blp_accounting.route("/accounting/vouchers", methods=["GET"])
class VoucherListResource(MethodView):
    @token_required
    @blp_accounting.arguments(VoucherListQuerySchema, location="query")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="List payment vouchers", security=[{"Bearer":[]}])
    def get(self, qd):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui, qd.get("business_id"))
        return prepared_response(True,"OK","Vouchers.",data=PaymentVoucher.get_all(bid, status=qd.get("status"), payee_id=qd.get("payee_id"), start_date=qd.get("start_date"), end_date=qd.get("end_date"), page=qd.get("page",1), per_page=qd.get("per_page",50)))

@blp_accounting.route("/accounting/voucher/approve", methods=["POST"])
class VoucherApproveResource(MethodView):
    @token_required
    @blp_accounting.arguments(VoucherApproveSchema, location="json")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Approve a payment voucher", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        existing = PaymentVoucher.get_by_id(d["voucher_id"], target_business_id)
        if not existing:
            Log.info(f"Voucher not found: {d['voucher_id']} for business {target_business_id}")
            return prepared_response(False, "NOT_FOUND", "Voucher not found.")

        if existing.get("status") != "Draft":
            Log.info(f"Voucher status conflict: {d['voucher_id']} is '{existing.get('status')}', not 'Draft'")
            return prepared_response(False, "CONFLICT", f"Voucher is '{existing.get('status')}', not Draft.")

        ok = PaymentVoucher.approve(d["voucher_id"], target_business_id, str(user_info.get("_id")))
        if ok:
            updated = PaymentVoucher.get_by_id(d["voucher_id"], target_business_id)
            return prepared_response(True, "OK", "Voucher approved.", data=updated)
        return prepared_response(False, "BAD_REQUEST", "Failed to approve voucher.")


@blp_accounting.route("/accounting/voucher/mark-paid", methods=["POST"])
class VoucherMarkPaidResource(MethodView):
    @token_required
    @blp_accounting.arguments(VoucherMarkPaidSchema, location="json")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Mark voucher as paid (optionally link to a transaction)", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        existing = PaymentVoucher.get_by_id(d["voucher_id"], target_business_id)
        if not existing:
            Log.info(f"Voucher not found: {d['voucher_id']} for business {target_business_id}")
            return prepared_response(False, "NOT_FOUND", "Voucher not found.")

        if existing.get("status") != "Approved":
            Log.info(f"Voucher status conflict: {d['voucher_id']} is '{existing.get('status')}', not 'Approved'")
            return prepared_response(False, "CONFLICT", f"Voucher is '{existing.get('status')}', not Approved.")

        txn_id = d.get("transaction_id")
        if txn_id:
            txn = Transaction.get_by_id(txn_id, target_business_id)
            if not txn:
                return prepared_response(False, "NOT_FOUND", f"Transaction '{txn_id}' not found.")

        ok = PaymentVoucher.mark_paid(d["voucher_id"], target_business_id, txn_id)
        if ok:
            updated = PaymentVoucher.get_by_id(d["voucher_id"], target_business_id)
            return prepared_response(True, "OK", "Voucher marked as paid.", data=updated)
        return prepared_response(False, "BAD_REQUEST", "Failed to mark as paid.")

# ════════════════════════════ BANK IMPORT ════════════════════════════

@blp_accounting.route("/accounting/bank-import/rule", methods=["POST","DELETE"])
class BankImportRuleResource(MethodView):
    @token_required
    @blp_accounting.arguments(BankImportRuleCreateSchema, location="json")
    @blp_accounting.response(201)
    @blp_accounting.doc(summary="Create an auto-categorisation rule for bank imports", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        account_id = json_data.get("account_id")
        if account_id:
            if not Account.get_by_id(account_id, target_business_id):
                return prepared_response(False, "NOT_FOUND", f"Account '{account_id}' not found.")

        category_id = json_data.get("category_id")
        if category_id:
            if not Category.get_by_id(category_id, target_business_id):
                return prepared_response(False, "NOT_FOUND", f"Category '{category_id}' not found.")

        fund_id = json_data.get("fund_id")
        if fund_id:
            if not Fund.get_by_id(fund_id, target_business_id):
                return prepared_response(False, "NOT_FOUND", f"Fund '{fund_id}' not found.")

        payee_id = json_data.get("payee_id")
        if payee_id:
            if not Payee.get_by_id(payee_id, target_business_id):
                return prepared_response(False, "NOT_FOUND", f"Payee '{payee_id}' not found.")

        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = str(user_info.get("_id"))

            r = BankImportRule(**json_data)
            rid = r.save()

            if not rid:
                return prepared_response(False, "BAD_REQUEST", "Failed to create rule.")

            created = BankImportRule._normalise(
                db.get_collection(BankImportRule.collection_name).find_one({"_id": ObjectId(rid)})
            )
            return prepared_response(True, "CREATED", "Rule created.", data=created)
        except Exception as e:
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


    @token_required
    @blp_accounting.arguments(BankImportRuleIdQuerySchema, location="query")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Delete a bank import rule", security=[{"Bearer": []}])
    def delete(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        rule_doc = db.get_collection(BankImportRule.collection_name).find_one(
            {"_id": ObjectId(qd["rule_id"]), "business_id": ObjectId(target_business_id)}
        )
        if not rule_doc:
            return prepared_response(False, "NOT_FOUND", "Bank import rule not found.")

        try:
            BankImportRule.delete(qd["rule_id"], target_business_id)
            return prepared_response(True, "OK", "Rule deleted.")
        except Exception as e:
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])

@blp_accounting.route("/accounting/bank-import/rules", methods=["GET"])
class BankImportRuleListResource(MethodView):
    @token_required
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="List all bank import auto-categorisation rules", security=[{"Bearer":[]}])
    def get(self):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui, request.args.get("business_id"))
        rules = BankImportRule.get_all(bid)
        return prepared_response(True,"OK","Rules.",data={"rules": rules, "count": len(rules)})

@blp_accounting.route("/accounting/bank-import", methods=["POST"])
class BankImportResource(MethodView):
    @token_required
    @blp_accounting.arguments(BankImportSchema, location="json")
    @blp_accounting.response(201)
    @blp_accounting.doc(summary="Import bank transactions (auto-categorises using rules)", description="Each imported transaction is matched against bank import rules for auto-categorisation.", security=[{"Bearer":[]}])
    def post(self, json_data):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui)
        account_id = json_data.get("account_id")

        acc = Account.get_by_id(account_id, bid)
        if not acc: 
            Log.info(f"Bank import failed: account not found: {account_id} for business {bid}")
            return prepared_response(False,"NOT_FOUND","Account not found.")

        created = 0; auto_categorised = 0; errors_list = []

        for idx, entry in enumerate(json_data.get("transactions", [])):
            try:
                desc = entry.get("description", "")
                amount = entry.get("amount", 0)
                tt = "Income" if amount > 0 else "Expense"
                abs_amount = abs(amount)

                # Match rule
                rule = BankImportRule.match_transaction(bid, desc)

                txn_data = {
                    "transaction_type": rule.get("transaction_type", tt) if rule else tt,
                    "amount": abs_amount,
                    "transaction_date": entry.get("date"),
                    "debit_account_id": account_id if tt == "Expense" else None,
                    "credit_account_id": account_id if tt == "Income" else None,
                    "description": desc,
                    "reference_number": entry.get("reference"),
                    "status": "Cleared",
                    "is_bank_imported": True,
                    "bank_transaction_id": entry.get("reference"),
                    "business_id": bid,
                    "user_id": ui.get("user_id"),
                    "user__id": str(ui.get("_id")),
                }

                if rule:
                    if rule.get("category_id"): txn_data["category_id"] = rule["category_id"]
                    if rule.get("fund_id"): txn_data["fund_id"] = rule["fund_id"]
                    if rule.get("payee_id"): txn_data["payee_id"] = rule["payee_id"]
                    if rule.get("account_id"): txn_data["credit_account_id" if tt=="Expense" else "debit_account_id"] = rule["account_id"]
                    auto_categorised += 1

                txn = Transaction(**txn_data)
                tid = txn.save()
                if tid:
                    Account.adjust_balance(account_id, bid, amount)
                    if txn_data.get("fund_id"):
                        Fund.adjust_balance(txn_data["fund_id"], bid, abs_amount if tt=="Income" else -abs_amount)
                    created += 1
                else:
                    errors_list.append({"row": idx+1, "error": "save failed"})
            except Exception as e:
                errors_list.append({"row": idx+1, "error": str(e)})

        return prepared_response(True,"CREATED",
            f"Import complete. {created} created, {auto_categorised} auto-categorised, {len(errors_list)} errors.",
            data={"created": created, "auto_categorised": auto_categorised, "errors": errors_list})


# ════════════════════════════ FINANCIAL DASHBOARD ════════════════════════════

@blp_accounting.route("/accounting/dashboard", methods=["GET"])
class FinancialDashboardResource(MethodView):
    @token_required
    @blp_accounting.arguments(FinancialDashboardQuerySchema, location="query")
    @blp_accounting.response(200)
    @blp_accounting.doc(summary="Financial dashboard with visual summary data", description="Returns income/expense totals, fund balances, budget utilisation, recent transactions.", security=[{"Bearer":[]}])
    def get(self, qd):
        ui = g.get("current_user",{}); bid = _resolve_business_id(ui, qd.get("business_id"))
        start = qd.get("start_date") or datetime.utcnow().strftime("%Y-01-01")
        end = qd.get("end_date") or datetime.utcnow().strftime("%Y-12-31")
        branch_id = qd.get("branch_id")

        try:
            ie = Transaction.get_income_expense_statement(bid, start, end, branch_id=branch_id)
            fund_sum = Fund.get_summary(bid)
            recent = Transaction.get_all(bid, page=1, per_page=10, start_date=start, end_date=end, branch_id=branch_id)

            # Monthly trends
            txn_coll = db.get_collection(Transaction.collection_name)
            match_q = {"business_id": ObjectId(bid), "transaction_date": {"$gte": start, "$lte": end}, "hashed_status": {"$ne": hash_data("Voided")}}
            if branch_id: match_q["branch_id"] = ObjectId(branch_id)

            pipeline = [
                {"$match": match_q},
                {"$addFields": {"month": {"$substr": ["$transaction_date", 0, 7]}}},
                {"$group": {"_id": {"month": "$month", "type": "$transaction_type"}, "total": {"$sum": "$amount"}}},
                {"$sort": {"_id.month": 1}},
            ]
            monthly_raw = list(txn_coll.aggregate(pipeline))
            monthly = {}
            for r in monthly_raw:
                m = r["_id"]["month"]; t = r["_id"]["type"]
                monthly.setdefault(m, {"month": m, "income": 0, "expense": 0})
                if t == "Income": monthly[m]["income"] = round(r["total"], 2)
                elif t == "Expense": monthly[m]["expense"] = round(r["total"], 2)
            for m in monthly.values():
                m["net"] = round(m["income"] - m["expense"], 2)


            return prepared_response(True,"OK","Financial dashboard.",data={
                "period": {"start": start, "end": end},
                "income_expense": ie,
                "fund_summary": fund_sum,
                "monthly_trends": list(monthly.values()),
                "recent_transactions": recent.get("transactions", [])[:10],
            })
        except Exception as e:
            Log.error(f"[FinancialDashboard] {e}")
            return prepared_response(False,"INTERNAL_SERVER_ERROR","Error.",errors=[str(e)])
