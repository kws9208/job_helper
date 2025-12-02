import os
from dotenv import load_dotenv
from dataclasses import dataclass

load_dotenv()

@dataclass
class Setting:
    # ATP settings
    ORACLE_USER = os.getenv("ORACLE_USER")
    ORACLE_PASSWORD = os.getenv("ORACLE_USER_PASSWORD")
    ORACLE_DSN = os.getenv("ORACLE_DSN")
    WALLET_DIR = os.getenv("WALLET_DIR")
    WALLET_PASSWORD = os.getenv("WALLET_PASSWORD")

    # NOSQL settings
    COMPARTMENT_OCID = os.getenv("COMPARTMENT_OCID")
    NOSQL_TABLE_NAME = os.getenv("NOSQL_TABLE_NAME")