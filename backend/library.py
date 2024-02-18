import json
import sqlite3
from datetime import datetime
from root import ROOT
import numpy as np


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
    now = f"{datetime.now().strftime('%Y-%m')}-01"
    end_date = end_date[:-2] + "-01" if end_date else None

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


def get_total_expenses_grouped_by_category(nb_months_ago: int, monthly: bool):  # eg -1 = last month
    # Query the expenses for calculations
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
    data = []
    for row in rows:
        category, price_fabian, price_elisa = row
        data.append(
            {
                "category": category,
                "price_fabian": price_fabian,
                "price_elisa": price_elisa,
            }
        )

    return data


def get_expenses(nb_months_ago, monthly=False):  # nb_months_ago: 0 = current month, -1 = last month, etc.

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
    data = []
    for row in rows:
        (id, date, price_person, price_other, paid_by, category, subcategories, descriptions) = row

        category = category.replace("null", "")
        subcategories = subcategories.replace("null", "") if subcategories else ""
        descriptions = descriptions.replace("null", "")

        individual_cost = {
            "id": id,
            "date": datetime.strptime(date, "%Y-%m-%d").strftime("%d-%m") if date else "00-00",
            "price_fabian": price_person,
            "price_elisa": price_other,
            "paid_by": paid_by,
            "category": category,
            "subcategory": subcategories,
            "description": descriptions,
        }

        data.append(individual_cost)

    return data


def delete_expense(id):
    # group: id: take the maximum
    query = """
        DELETE FROM expenses
        WHERE id = ?
        """,
    execute_sql_query(query, (id,))

    return True


def get_historic_descriptions() -> list:
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
