with staged_orders as (

    select
        order_id,
        customer_name,
        order_status,
        amount,
        created_at,
        updated_at
    from {{ ref('stg_orders') }}

)

select
    order_id,
    customer_name,
    order_status,
    amount,
    date(created_at) as order_date,
    order_status = 'paid' as is_paid,

    case
        when order_status = 'paid' then amount
        else cast(0 as numeric)
    end as paid_amount,

    case
        when order_status = 'pending' then amount
        else cast(0 as numeric)
    end as pending_amount,

    created_at,
    updated_at
from staged_orders