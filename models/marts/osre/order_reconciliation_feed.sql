with staged_orders as (

    select
        order_id,
        order_status,
        amount,
        updated_at
    from {{ ref('stg_orders') }}

)

select
    order_id,
    amount,
    order_status as source_order_status,

    case
        when order_status = 'paid'
            then 'ready_for_reconciliation'
        when order_status = 'pending'
            then 'waiting_for_payment'
    end as reconciliation_status,

    updated_at as source_updated_at
from staged_orders