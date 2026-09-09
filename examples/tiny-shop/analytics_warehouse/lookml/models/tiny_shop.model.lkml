# Tiny Shop model.
#
# Built on the layered LookML architecture: droughty generates the base and
# aggregate layers, and the staging and aggregate layers refine them by hand.
# Regenerating the base layers does not lose the hand-written work.

connection: "bq-tiny-shop"

label: "Tiny Shop Analytics Warehouse"

week_start_day: monday

# Include every explore and layer from the integration layer.
include: "/analytics_warehouse/lookml/int/*.explore.lkml"

# --------------------------------------------------------------------------------------------------------
# Data groups (caching policies)
# --------------------------------------------------------------------------------------------------------

datagroup: daily_datagroup {
  label: "Daily"
  sql_trigger: select current_date() ;;
  max_cache_age: "24 hours"
  description: "Refreshes once the daily build has run."
}
