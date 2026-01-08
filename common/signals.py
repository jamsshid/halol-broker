from django.dispatch import Signal

# Account signals
account_created = Signal()  # providing_args=['account']
account_status_changed = (
    Signal()
)  # providing_args=['account', 'old_status', 'new_status']
balance_updated = Signal()  # providing_args=['account', 'old_balance', 'new_balance']

# Transaction signals
transaction_completed = Signal()  # providing_args=['transaction']
deposit_completed = Signal()  # providing_args=['deposit']
withdrawal_completed = Signal()  # providing_args=['withdrawal']

# Risk signals
daily_loss_limit_exceeded = Signal()  # providing_args=['account']
margin_call_triggered = Signal()  # providing_args=['account']
stop_out_triggered = Signal()
