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

    # Pricing (Yeh add kiya gaya hai)
    PRICING = {
        "UK": {
            "FTID": 15,
            "LIT": 20,
            "RM_RTS": 20,
            "Receipt": 5
        },
        "USA": {"FTID": 15, "UPS_LIT": 20},
        "Spain": {"FTID": 30},
        "Germany": {"FTID": 30},
        "Italy": {"FTID": 30},
        "France": {"FTID": 30}
    }

    # UK Carriers
    UK_CARRIERS = ["Royal Mail", "DPD", "Evri", "DHL", "FedEx", "Parcelforce", "InPost", "UPS"]
    
    # Countries
    COUNTRIES = ["United Kingdom", "USA", "Spain", "Germany", "Italy", "France"]