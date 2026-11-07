from decimal import Decimal
from common import encode
from operating import build_company_pack, validate_pack
from cash_engine import project
from valuation import terminal_contract, values
import tax_bridge

class QuietJournal:
    def event(self, *args): pass
    def save(self, *args): pass

def calculate(inputs):
    # Operating budgets are freshly generated from their original facts and assumptions.
    # The adopted tax, legal-cash and equity bridge consumes this actual pack.
    journal = QuietJournal()
    tax_bridge.config(inputs)
    pack = build_company_pack(inputs, journal)
    validate_pack(pack)
    projection = project(inputs, pack, journal)
    terminal = terminal_contract(inputs, pack, projection, journal)
    result = values(inputs, pack, projection, terminal, journal)
    if result["full_projection"]["funding_failures"]:
        raise ValueError("采用基准的资金路径未通过")
    value = float(result["current"]["A"]["per_share"].quantize(Decimal(".01")))
    terminal = float(result["Y5"]["A"]["per_share"])
    holder = {"base_case_distributions_per_share": [float(x) for x in result["D"]],
              "base_case_terminal_equity_value_range_per_share": {"year_5": {"low": terminal, "high": terminal}}}
    return {"low": value, "high": value, "currency": "CNY"}, holder, result
