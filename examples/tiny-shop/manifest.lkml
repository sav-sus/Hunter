project_name: "tiny-shop"

# Connection
constant: shop_connection {
  value: "bq-tiny-shop"
  export: override_optional
}

# BigQuery project and dataset
constant: shop_gcp_project {
  value: "pj-tiny-shop-warehouse-dev"
  export: override_optional
}

constant: shop_schema {
  value: "analytics_warehouse"
  export: override_optional
}
