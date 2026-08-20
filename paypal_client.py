import paypalrestsdk
from config import Config

# Configure PayPal SDK
paypalrestsdk.configure({
    "mode": Config.PAYPAL_MODE,  # sandbox or live
    "client_id": Config.PAYPAL_CLIENT_ID,
    "client_secret": Config.PAYPAL_SECRET
})

def create_payment(amount, currency="GBP", description="Label Service"):
    """Create a PayPal payment and return payment object with approval URL"""
    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {
            "payment_method": "paypal"
        },
        "redirect_urls": {
            "return_url": "https://zaplabels.com/success",
            "cancel_url": "https://zaplabels.com/cancel"
        },
        "transactions": [{
            "item_list": {
                "items": [{
                    "name": description,
                    "sku": "label",
                    "price": str(amount),
                    "currency": currency,
                    "quantity": 1
                }]
            },
            "amount": {
                "total": str(amount),
                "currency": currency
            },
            "description": f"Payment for {description}"
        }]
    })
    
    if payment.create():
        print(f"✅ Payment created: {payment.id}")
        # Find approval URL
        for link in payment.links:
            if link.rel == "approval_url":
                return payment, link.href
        return payment, None
    else:
        print(f"❌ Error creating payment: {payment.error}")
        return None, None

def execute_payment(payment_id, payer_id):
    """Execute a PayPal payment"""
    payment = paypalrestsdk.Payment.find(payment_id)
    
    if payment.execute({"payer_id": payer_id}):
        print(f"✅ Payment executed: {payment.id}")
        return payment
    else:
        print(f"❌ Error executing payment: {payment.error}")
        return None