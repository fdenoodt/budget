import json
import sqlite3
from datetime import datetime

from expense import Expense
from grouped_expense import GroupedExpense
from root import ROOT
import numpy as np
from typing import List

from savings_pairs import SavingsTuple
import pytz


def param(name):
    with open(f"{ROOT}params.json") as f:
        data = json.load(f)
        return data[name]


def execute_sql_query(query, params=()):
    with sqlite3.connect(f"{ROOT}/expenses.db") as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()


def add_expense(price_fabian, price_elisa, paid_by, category, description, subcategory, now):
    query = """
        INSERT INTO expenses (date, price_fabian, price_elisa, paid_by, category, description, subcategory)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
    params = (now.strftime("%Y-%m-%d"), price_fabian, price_elisa, paid_by.lower(), category, description, subcategory)
    execute_sql_query(query, params)


def get_debt_per_person():
    fabian1, elisa1 = _get_debt_per_person()
    fabian2, elisa2 = _get_debt_per_person_monthly()
    fabian = fabian1 + fabian2
    elisa = elisa1 + elisa2

    return fabian, elisa


def _get_active_months(start_date, end_date):
    # don't consider the day
    start_date = start_date[:-2] + "01"  # eg: '2023-12-25' -> '2023-12-01'
    # now = f"{datetime.now().strftime('%Y-%m')}-01"
    now = f"{datetime.now(pytz.timezone('Europe/Brussels')).strftime('%Y-%m')}-01"  # make it timezone aware
    end_date = end_date[:-2] + "01" if end_date else None

    if end_date is None or end_date == "":
        days = (datetime.strptime(now, "%Y-%m-%d") - datetime.strptime(start_date, "%Y-%m-%d")).days / 30
    else:
        days = (datetime.strptime(end_date, "%Y-%m-%d") - datetime.strptime(start_date, "%Y-%m-%d")).days / 30

    return np.ceil(days)


def _get_debt_per_person_monthly():
    # other function `_get_debt_per_person` only works if cost is only once. as soon as it's monthly, it doesn't work anymore as only counted once.
    # So needs to multiply by the number of months

    query = f"""
        SELECT price_fabian, price_elisa, paid_by, start_date, end_date FROM monthly_expenses
        WHERE strftime('%Y-%m', start_date) <= strftime('%Y-%m', 'now') and 
        (strftime('%Y-%m', end_date) >= strftime('%Y-%m', 'now') OR end_date IS NULL OR end_date = '')
        """
    rows = execute_sql_query(query)

    # for each row multiply by the number of months it has been active
    fabian = 0
    elisa = 0
    for row in rows:
        price_fabian, price_elisa, paid_by, start_date, end_date = row
        if paid_by.lower() == "fabian":
            # fabian paid `price_elisa` for elisa so Elisa has debt
            elisa += price_elisa * _get_active_months(start_date, end_date)
        elif paid_by.lower() == "elisa":
            fabian += price_fabian * _get_active_months(start_date, end_date)
        else:
            raise ValueError("Invalid value for `paid_by`")
            print(
                f"nb_months: {_get_active_months(start_date, end_date)} paid by: {paid_by} price_fabian: {price_fabian} price_elisa: {price_elisa}")

    return fabian, elisa


def _get_debt_per_person():
    query = f"""
        SELECT price_fabian, price_elisa, paid_by FROM expenses
        """
    rows = execute_sql_query(query)

    # Perform debt calculations based on fetched data
    fabian = 0
    elisa = 0
    for row in rows:
        price_fabian, price_elisa, paid_by = row
        if paid_by.lower() == "fabian":
            # fabian paid `price_elisa` for elisa so Elisa has debt
            elisa += price_elisa
        elif paid_by.lower() == "elisa":
            fabian += price_fabian
        else:
            raise ValueError("Invalid value for `paid_by`")

    return fabian, elisa


def get_total_expenses_grouped_by_category(nb_months_ago: int, monthly: bool) -> List[GroupedExpense]:
    # eg -1 = last month
    if not monthly:
        query = (f"""
            SELECT category, sum(price_fabian), sum(price_elisa) FROM expenses
            WHERE strftime('%Y-%m', date) = strftime('%Y-%m', 'now', '{nb_months_ago} months')
            GROUP BY category
            """)
    else:
        query = (f"""
            SELECT category, sum(price_fabian), sum(price_elisa) FROM monthly_expenses
            WHERE strftime('%Y-%m', start_date) <= strftime('%Y-%m', 'now', '{nb_months_ago} months') and
            (strftime('%Y-%m', end_date) >= strftime('%Y-%m', 'now', '{nb_months_ago} months') OR end_date IS NULL OR end_date = '')
            GROUP BY category
            """)

    rows = execute_sql_query(query)
    # Perform debt calculations based on fetched data
    data: List[GroupedExpense] = []
    for row in rows:
        category, price_fabian, price_elisa = row
        data.append(GroupedExpense(category, price_fabian, price_elisa))

    return data


def get_expenses(nb_months_ago, monthly=False) -> List[Expense]:
    # nb_months_ago: 0 = current month, -1 = last month, etc.

    if not monthly:
        # Expenses of `nb_months_ago` months ago
        query_indiv = f"""
                SELECT id, date, price_fabian, price_elisa, paid_by, category, subcategory, description
                FROM expenses
                WHERE strftime('%Y-%m', date) = strftime('%Y-%m', 'now', '{nb_months_ago} months')
                ORDER by date DESC, id DESC
                """
    else:
        # Expenses of `nb_months_ago` months ago. (records don't have date, but instead start_date and end_date)
        query_indiv = f"""
                SELECT id, null as date, price_fabian, price_elisa, paid_by, category, subcategory, description
                FROM monthly_expenses
                WHERE strftime('%Y-%m', start_date) <= strftime('%Y-%m', 'now', '{nb_months_ago} months') and
                (strftime('%Y-%m', end_date) >= strftime('%Y-%m', 'now', '{nb_months_ago} months') OR end_date IS NULL OR end_date = '')
                ORDER by start_date DESC, id DESC
                """

    rows = execute_sql_query(query_indiv)

    # Perform expense calculations based on fetched data
    data: List[Expense] = []
    for row in rows:
        (id, date, price_person, price_other, paid_by, category, subcategories, descriptions) = row

        category = category.replace("null", "")
        subcategories = subcategories.replace("null", "") if subcategories else ""
        descriptions = descriptions.replace("null", "")

        individual_cost = Expense(id, date, price_person, price_other, paid_by, category, subcategories, descriptions)
        data.append(individual_cost)

    return data


def delete_expense(id: int):
    # group: id: take the maximum
    query = """DELETE FROM expenses WHERE id = ?"""
    execute_sql_query(query, (id,))

    return True


def edit_expense(id: int, date: str):
    """
    :param id: int
    :param date: str in format 'DD/MM/YYYY'
    :return:
    """
    date = datetime.strptime(date, "%d/%m/%Y").strftime("%Y-%m-%d")
    query = """UPDATE expenses SET date = ? WHERE id = ?"""
    execute_sql_query(query, (date, id))

    return True


def get_historic_descriptions() -> List[str]:
    # Query the UNIQ list
    query = """
        SELECT DISTINCT description FROM expenses
        WHERE description IS NOT NULL
        """

    rows = execute_sql_query(query)
    categories = [row[0] for row in rows]

    # remove `null` from the list
    categories = [c for c in categories if c != "null"]
    return categories


def _get_all_savings_for_each_month(who: str, up_to: int) -> List[SavingsTuple]:
    # Returns a list where list[i] is the sum of all expenses of `who` for the month at `i` months ago
    # Last record is the current month

    # up_to : 0 = current month, -1 = last month, etc.

    def _get_money_saved(expenses, expenses_periodic):
        # returns the money saved for the month
        sum_expense = sum([e.price_fabian if who == 'fabian' else e.price_elisa for e in expenses])
        sum_expense += sum([e.price_fabian if who == 'fabian' else e.price_elisa for e in expenses_periodic])
        sum_expense += RENT_COST

        savings = sum_expense * -1  # st it's positive if it's a saving, negative if there's debt that month
        return savings

    def _get_income(expenses, who):
        # get all negative items in sum_expenses
        neg_expenses: List[Expense] = [exp for exp in expenses
                                       if exp.price_elisa + exp.price_fabian < 0]  # = all incomes
        total_income = sum([e.price_fabian if who == 'fabian' else e.price_elisa for e in neg_expenses]) * -1
        return total_income

    RENT_COST = 455
    MONTHLY_ALLOWANCE = 800

    # VALUES COMPUTED ON SALARY - RENT - MONTHLY_ALLOWANCE
    if who.lower() == 'fabian':
        INVESTMENT_PERCENT = .85
    else: # elisa
        INVESTMENT_PERCENT = .82
    MONEY_PIG_PERCENT = 1 - INVESTMENT_PERCENT  # 20% of the money saved goes to the pig

    # e.g. income = 2700 - 455 - 800 = 1445.
    # 1445*80% = 1156 goes to investments
    # 1445*20% = 289 goes to pig

    sum_expenses: List[SavingsTuple] = []
    nb_months_ago = 0

    while True:
        # Get all expenses/periodic expenses/incomes for the month at `nb_months_ago` months ago
        # income is negative val
        # cost is positive val
        expenses: List[Expense] = get_expenses(nb_months_ago)
        expenses_periodic = get_expenses(nb_months_ago, monthly=True)
        if len(expenses) == 0:
            break

        actual_savings_full = _get_money_saved(expenses, expenses_periodic)  # higher = more saved
        income = _get_income(expenses, who)  # higher = more income
        target_full = income - MONTHLY_ALLOWANCE - RENT_COST

        target_only_investments = target_full * INVESTMENT_PERCENT
        target_only_pig = target_full * MONEY_PIG_PERCENT

        actual_only_pig = actual_savings_full - target_only_investments  # regardless of actual spending, we always invest the same target amount!
        actual_only_investments = target_only_investments

        sum_expenses.append(SavingsTuple(actual_full=actual_savings_full,
                                         target_full=target_full,

                                         target_only_pig=target_only_pig,
                                         target_only_investments=target_only_investments,

                                         actual_only_pig=actual_only_pig,
                                         actual_only_investments=actual_only_investments,
                                         nb_months_ago=nb_months_ago))
        nb_months_ago -= 1

    # reverse the list so that the last record is the current month
    sum_expenses = sum_expenses[::-1]

    # remove first elt (somehow first is strange output)
    sum_expenses = sum_expenses[1:]

    if up_to == 0:
        return sum_expenses
    else:
        return sum_expenses[:up_to]


def _get_all_earnings_for_each_month(who: str, up_to: int) -> List[float]:
    # Returns a list where list[i] is the sum of all expenses of `who` for the month at `i` months ago
    # Last record is the current month

    # up_to : 0 = current month, -1 = last month, etc.

    sum_incomes_per_month: List[float] = []
    nb_months_ago = 0

    while True:
        # Get all expenses for the month at `nb_months_ago` months ago
        expenses: List[Expense] = get_expenses(nb_months_ago)
        expenses_periodic: List[Expense] = get_expenses(nb_months_ago, monthly=True)
        if len(expenses) == 0:
            break

        # filter expenses of category 'Inkomst'
        incomes: List[Expense] = [e for e in expenses if e.category == 'Inkomst']
        incomes_periodic = [e for e in expenses_periodic if e.category == 'Inkomst']

        sum_income = sum([e.price_fabian if who == 'fabian' else e.price_elisa for e in incomes])
        sum_income += sum([e.price_fabian if who == 'fabian' else e.price_elisa for e in incomes_periodic])
        sum_incomes_per_month.append(
            sum_income * -1)  # st it's positive if it's a saving, negative if there's debt that month

        nb_months_ago -= 1

    # reverse the list so that the last record is the current month, and *-1 to make it positive, and remove first elt
    incomes_most_recent_first = sum_incomes_per_month[::-1][1:]

    # rm up_to
    if up_to == 0:
        return incomes_most_recent_first
    else:
        return incomes_most_recent_first[:up_to]  # e.g. [:-3] = all but last 3


def _get_last_n_days_expenses(n: int) -> List[Expense]:
    # Returns a list of all expenses of `who` for the last 5 days
    query = f"""
        SELECT id, date, price_fabian, price_elisa, paid_by, category, subcategory, description
        FROM expenses
        WHERE date >= date('now', '-{n} days')
        """
    rows = execute_sql_query(query)

    # Perform expense calculations based on fetched data
    data: List[Expense] = []
    for row in rows:
        (id, date, price_person, price_other, paid_by, category, subcategories, descriptions) = row

        category = category.replace("null", "")
        subcategories = subcategories.replace("null", "") if subcategories else ""
        descriptions = descriptions.replace("null", "")

        # filter out incomes
        if category.lower() == "inkomst" or price_person < 0 or price_other < 0:
            continue

        individual_cost = Expense(id, date, price_person, price_other, paid_by, category, subcategories, descriptions)
        data.append(individual_cost)

    return data
