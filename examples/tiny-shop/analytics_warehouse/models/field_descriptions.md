{% docs order_pk %}
Surrogate key for the order.
{% enddocs %}

{% docs customer_fk %}
The customer who placed the order.
{% enddocs %}

{% docs order_natural_key %}
The order reference from the shop platform.
{% enddocs %}

{% docs order_total_amount %}
Order value before returns, in the order's own currency.
{% enddocs %}

{% docs customer_pk %}
Surrogate key for the customer.
{% enddocs %}

{% docs customer_name %}
Customer name, as the shop platform holds it.
{% enddocs %}

{% docs product_pk %}
Surrogate key for the product.
{% enddocs %}

{% docs supplier_pk %}
Surrogate key for the supplier. Written before the table was built, so nothing
references it. Hunter reports it as an orphaned description.
{% enddocs %}
