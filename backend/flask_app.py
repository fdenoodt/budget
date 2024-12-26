import json
from datetime import datetime
from typing import List

import seaborn as sns
from flask_httpauth import HTTPBasicAuth
from flask import Flask, request
from flask_cors import CORS

from expense import Expense
from grouped_expense import GroupedExpense
from savings_pairs import SavingsPair
from library import (
    add_expense,
    get_debt_per_person,
    get_expenses,
    param,
    delete_expense, edit_expense, get_total_expenses_grouped_by_category, get_historic_descriptions,
    _get_all_savings_for_each_month, _get_all_earnings_for_each_month,
)

sns.set_theme()

app = Flask(__name__)
CORS(app, resources={r"*": {"origins": "*"}})
auth = HTTPBasicAuth()


@auth.verify_password
def verify_password(username, password):
    if username == "fabian" and password == "cool":
        return username


# returns bot debts and all expenses
class IndexResponse:
    def __init__(self, fabian: float, elisa: float,
                 fabian_earnings_of_lifetime: List[float], elisa_earnings_of_lifetime: List[float],
                 expenses: List[Expense], grouped_expenses: List[GroupedExpense],
                 monthly_expenses: List[Expense], monthly_grouped_expenses: List[GroupedExpense],
                 historic_descriptions: List[str],
                 savings_of_lifetime_fabian: List[SavingsPair], savings_of_lifetime_elisa: List[SavingsPair]):
        self.fabian = fabian  # debt
        self.elisa = elisa  # debt

        # monthly earnings (list)
        self.fabian_earnings_of_lifetime: List[float] = fabian_earnings_of_lifetime
        self.elisa_earnings_of_lifetime: List[float] = elisa_earnings_of_lifetime

        self.expenses = expenses
        self.grouped_expenses = grouped_expenses
        self.monthly_expenses = monthly_expenses
        self.monthly_grouped_expenses = monthly_grouped_expenses
        self.historic_descriptions = historic_descriptions
        self.savings_of_lifetime_fabian = savings_of_lifetime_fabian
        self.savings_of_lifetime_elisa = savings_of_lifetime_elisa

    def serialize(self) -> dict:
        return {
            "fabian": self.fabian,  # debt
            "elisa": self.elisa,

            "expenses": [e.serialize() for e in self.expenses],
            "grouped_expenses": [e.serialize() for e in self.grouped_expenses],
            "monthly_expenses": [e.serialize() for e in self.monthly_expenses],
            "monthly_grouped_expenses": [e.serialize() for e in self.monthly_grouped_expenses],
            "historic_descriptions": self.historic_descriptions,

            "fabian_earnings_of_lifetime": self.fabian_earnings_of_lifetime,
            "elisa_earnings_of_lifetime": self.elisa_earnings_of_lifetime,

            "savings_of_lifetime_fabian": [e.serialize() for e in self.savings_of_lifetime_fabian],  # [SavingsPair]
            "savings_of_lifetime_elisa": [e.serialize() for e in self.savings_of_lifetime_elisa]
        }


@app.route("/")
@auth.login_required
def page_index():
    nb_months_ago = int(request.args.get("month"))  # 0 = current month, -1 = last month, etc.

    # get debt per person
    fabian, elisa = get_debt_per_person()
    # round to 2 decimals
    fabian = round(fabian, 2)
    elisa = round(elisa, 2)

    # get all expenses
    expenses: List[Expense] = get_expenses(nb_months_ago, monthly=False)
    monthly_expenses: List[Expense] = get_expenses(nb_months_ago, monthly=True)

    # get debts per category from current month
    grouped_expenses: List[GroupedExpense] = get_total_expenses_grouped_by_category(nb_months_ago, monthly=False)
    monthly_grouped_expenses: List[GroupedExpense] = get_total_expenses_grouped_by_category(nb_months_ago, monthly=True)

    historic_descriptions: List[str] = get_historic_descriptions()  # eg: ["colruyt", "aldi", "carrefour", ...]

    # A list st list[i] is all expenses/incomes for month i. Last record is the current month
    savings_of_lifetime_fabian: List[SavingsPair] = _get_all_savings_for_each_month("fabian")
    savings_of_lifetime_elisa: List[SavingsPair] = _get_all_savings_for_each_month("elisa")

    # Monthly earnings
    fabian_earnings_of_lifetime = _get_all_earnings_for_each_month("fabian")
    elisa_earnings_of_lifetime = _get_all_earnings_for_each_month("elisa")

    return_data = IndexResponse(fabian, elisa,
                                fabian_earnings_of_lifetime, elisa_earnings_of_lifetime,
                                expenses, grouped_expenses,
                                monthly_expenses, monthly_grouped_expenses,
                                historic_descriptions,
                                savings_of_lifetime_fabian, savings_of_lifetime_elisa)

    return json.dumps(return_data.serialize())


@auth.login_required
@app.route("/add_expense")
def page_add_expense():
    # retrieve params: price, ratio, category
    r = request
    price_fabian = float(r.args.get("price_fabian"))
    price_elisa = float(r.args.get("price_elisa"))
    paid_by = r.args.get("paid_by")
    category = r.args.get("category")
    subcategory = r.args.get("subcategory")
    description = r.args.get("description")
    now = datetime.now()

    add_expense(
        price_fabian, price_elisa, paid_by, category, description, subcategory, now
    )
    return json.dumps({"message": "Expense added"})


@auth.login_required
@app.route("/delete_expense")
def page_delete_expense():
    # retrieve params: price, ratio, category
    r = request
    id = int(r.args.get("id"))

    delete_expense(id)
    return json.dumps({"message": "Expense deleted"})


@auth.login_required
@app.route("/edit_expense")
def page_edit_expense():
    r = request
    id = int(r.args.get("id"))
    date = r.args.get("date")

    edit_expense(id, date)
    return json.dumps({"message": "Expense edited"})


if not (param("isServer")):
    app.run()
