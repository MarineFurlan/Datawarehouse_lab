with source_orders as (

    select *
    from {{ source('oei_einvoice', 'orders') }}

),

cleaned_orders as (

    select
        cast(order_id as int64) as order_id,
        trim(customer_name) as customer_name,
        lower(trim(order_status)) as order_status,
        cast(amount as numeric) as amount,
        cast(created_at as timestamp) as created_at,
        cast(updated_at as timestamp) as updated_at
    from source_orders

)

select *
from cleaned_orders
