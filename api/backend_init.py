"""Docker backend initializer with on-demand legacy AI tool loading."""

from importlib import import_module

tools_mapping: dict[str, object] = {}

_TOOLS = {
    "inventory": "check_inventory get_all_inventory get_low_stock_inventory update_inventory rollback_inventory get_inventory_total_value get_cost_analysis calculate_smart_restocking",
    "orders": "get_recent_orders create_order cancel_order get_receivables get_customers_list get_quotations_summary",
    "procurement": "create_purchase_order get_payables get_suppliers_list get_purchase_orders_summary",
    "erp_exchange": "sync_external_purchase_order",
    "finance": "get_ledger_summary get_financial_overview calculate",
    "hr": "get_employee_info get_payroll_summary get_attendance_summary",
    "manufacturing": "get_bom_list get_work_orders_status",
    "carbon": "get_carbon_emissions_by_month get_carbon_emissions_by_year get_carbon_footprint_report get_esg_targets",
    "ai_supply_chain": "get_supply_chain_risk_events get_impacted_purchase_orders get_supply_chain_heatmap_summary",
}


def init_ai_tools() -> None:
    if tools_mapping:
        return
    for module_name, names in _TOOLS.items():
        module = import_module(f"backend.{module_name}")
        for name in names.split():
            tools_mapping[name] = getattr(module, name)
