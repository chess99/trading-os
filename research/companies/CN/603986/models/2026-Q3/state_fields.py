"""Pure field projection from the newly executed complete operating CLI; no valuation."""
import hashlib
import json
import sys
from pathlib import Path

FIELD_MAP = {
 'source_scenario':['scenario'],
 'old_current_primary_equity':['current_primary_equity'],
 'old_current_primary_per_share':['current_primary_per_diluted_share'],
 'old_current_range':['current_value_range_per_diluted_share'],
 'current_diluted_shares_m':['current_diluted_shares_m'],
 'old_primary_operating_value':['primary_operating_value'],
 'old_auxiliary_reference':['auxiliary'],
 'financial_bridge':['bridge'],
 'source_subscription_cash_pv':['future_subscription_cash_pv'],
 'holder':['holder'],
 'original_return_model':['return_model'],
 'source_parameter_points':['base_path_valuation_band']}
CX5_KEYS=['liquid_financial_assets_end','financing_liabilities_end','noncash_investments_fair_end','unknown_assets_fair_end','unknown_liabilities_end','fair_nonoperating_rights_end']
