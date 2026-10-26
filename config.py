import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    ADMIN_ID = int(os.getenv("ADMIN_ID", "8619429877"))
    PAYPAL_EMAIL = os.getenv("PAYPAL_EMAIL", "")
    
    PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
    PAYPAL_SECRET = os.getenv("PAYPAL_SECRET", os.getenv("PAYPAL_CLIENT_SECRET", ""))
    PAYPAL_MODE = os.getenv("PAYPAL_MODE", "sandbox")  # sandbox ya live

    # UK Carriers
    UK_CARRIERS = ["Royal Mail", "DPD", "Evri", "DHL", "FedEx", "Parcelforce", "InPost", "UPS"]
    
    # Countries
    COUNTRIES = ["United Kingdom", "USA", "Spain", "Germany", "Italy", "France"]