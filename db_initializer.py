import os
import certifi
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

def db_initializer():
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise ConnectionError("MONGO_URI is not defined in the environment variables.")
    try:
        print("Connecting to MongoDB...")
        client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
        db = client["enterprise_loans_db"]
        collection = db["loan_applications"]
        collection.drop()
        print("Dropped existing loan_applications collection.")

        loan_data = [
            # ── Record 1 ─────────────────────────────────────────────────────
            {
                "application_id": "LOAN-2026-001",
                "status": "Approved",
                "requested_amount": 75000,
                "term_months": 36,
                "financials": {
                    "annual_income": 115000,
                    "credit_score": 740,
                    "existing_debt": 12000
                },
                "customer": {
                    "first_name": "Deepak",
                    "last_name": "Sharma",
                    "email": "deepak.sharma@example.com",
                    "phone": "+91-98765-43210",
                    "address": {
                        "street": "45 MG Road, Phase 2",
                        "city": "Bangalore",
                        "state": "Karnataka",
                        "zip": "560001"
                    }
                }
            },
            # ── Record 2 ─────────────────────────────────────────────────────
            {
                "application_id": "LOAN-2026-002",
                "status": "Pending",
                "requested_amount": 250000,
                "term_months": 60,
                "financials": {
                    "annual_income": 95000,
                    "credit_score": 620,
                    "existing_debt": 45000
                },
                "customer": {
                    "first_name": "Priya",
                    "last_name": "Patel",
                    "email": "priya.p@example.com",
                    "phone": "+91-87654-32109",
                    "address": {
                        "street": "12 Juhu Tara Road",
                        "city": "Mumbai",
                        "state": "Maharashtra",
                        "zip": "400049"
                    }
                }
            },
            # ── Record 3 ─────────────────────────────────────────────────────
            {
                "application_id": "LOAN-2026-003",
                "status": "Approved",
                "requested_amount": 180000,
                "term_months": 48,
                "financials": {
                    "annual_income": 210000,
                    "credit_score": 780,
                    "existing_debt": 20000
                },
                "customer": {
                    "first_name": "Rahul",
                    "last_name": "Mehta",
                    "email": "rahul.mehta@example.com",
                    "phone": "+91-99001-12345",
                    "address": {
                        "street": "7 Linking Road, Bandra West",
                        "city": "Mumbai",
                        "state": "Maharashtra",
                        "zip": "400050"
                    }
                }
            },
            # ── Record 4 ─────────────────────────────────────────────────────
            {
                "application_id": "LOAN-2026-004",
                "status": "Rejected",
                "requested_amount": 500000,
                "term_months": 84,
                "financials": {
                    "annual_income": 72000,
                    "credit_score": 510,
                    "existing_debt": 130000
                },
                "customer": {
                    "first_name": "Ananya",
                    "last_name": "Krishnan",
                    "email": "ananya.k@example.com",
                    "phone": "+91-94433-77890",
                    "address": {
                        "street": "23 Anna Salai",
                        "city": "Chennai",
                        "state": "Tamil Nadu",
                        "zip": "600002"
                    }
                }
            },
            # ── Record 5 ─────────────────────────────────────────────────────
            {
                "application_id": "LOAN-2026-005",
                "status": "Approved",
                "requested_amount": 120000,
                "term_months": 24,
                "financials": {
                    "annual_income": 175000,
                    "credit_score": 810,
                    "existing_debt": 5000
                },
                "customer": {
                    "first_name": "Vikram",
                    "last_name": "Reddy",
                    "email": "vikram.r@example.com",
                    "phone": "+91-96321-55432",
                    "address": {
                        "street": "88 Jubilee Hills Road No. 36",
                        "city": "Hyderabad",
                        "state": "Telangana",
                        "zip": "500033"
                    }
                }
            },
            # ── Record 6 ─────────────────────────────────────────────────────
            {
                "application_id": "LOAN-2026-006",
                "status": "Pending",
                "requested_amount": 350000,
                "term_months": 72,
                "financials": {
                    "annual_income": 88000,
                    "credit_score": 655,
                    "existing_debt": 60000
                },
                "customer": {
                    "first_name": "Sneha",
                    "last_name": "Gupta",
                    "email": "sneha.gupta@example.com",
                    "phone": "+91-97112-34567",
                    "address": {
                        "street": "14 Connaught Place",
                        "city": "Delhi",
                        "state": "Delhi",
                        "zip": "110001"
                    }
                }
            },
            # ── Record 7 ─────────────────────────────────────────────────────
            {
                "application_id": "LOAN-2026-007",
                "status": "Approved",
                "requested_amount": 90000,
                "term_months": 36,
                "financials": {
                    "annual_income": 140000,
                    "credit_score": 760,
                    "existing_debt": 15000
                },
                "customer": {
                    "first_name": "Arjun",
                    "last_name": "Nair",
                    "email": "arjun.nair@example.com",
                    "phone": "+91-98001-23456",
                    "address": {
                        "street": "5 MG Road, Indiranagar",
                        "city": "Bangalore",
                        "state": "Karnataka",
                        "zip": "560038"
                    }
                }
            },
            # ── Record 8 ─────────────────────────────────────────────────────
            {
                "application_id": "LOAN-2026-008",
                "status": "Rejected",
                "requested_amount": 420000,
                "term_months": 60,
                "financials": {
                    "annual_income": 65000,
                    "credit_score": 490,
                    "existing_debt": 200000
                },
                "customer": {
                    "first_name": "Meera",
                    "last_name": "Joshi",
                    "email": "meera.joshi@example.com",
                    "phone": "+91-93322-11098",
                    "address": {
                        "street": "32 Koregaon Park Road",
                        "city": "Pune",
                        "state": "Maharashtra",
                        "zip": "411001"
                    }
                }
            },
            # ── Record 9 ─────────────────────────────────────────────────────
            {
                "application_id": "LOAN-2026-009",
                "status": "Pending",
                "requested_amount": 150000,
                "term_months": 48,
                "financials": {
                    "annual_income": 105000,
                    "credit_score": 690,
                    "existing_debt": 30000
                },
                "customer": {
                    "first_name": "Rohan",
                    "last_name": "Sharma",
                    "email": "rohan.sharma@example.com",
                    "phone": "+91-91234-56789",
                    "address": {
                        "street": "9 Park Street",
                        "city": "Kolkata",
                        "state": "West Bengal",
                        "zip": "700016"
                    }
                }
            },
            # ── Record 10 ────────────────────────────────────────────────────
            {
                "application_id": "LOAN-2026-010",
                "status": "Approved",
                "requested_amount": 60000,
                "term_months": 12,
                "financials": {
                    "annual_income": 195000,
                    "credit_score": 820,
                    "existing_debt": 3000
                },
                "customer": {
                    "first_name": "Kavya",
                    "last_name": "Menon",
                    "email": "kavya.menon@example.com",
                    "phone": "+91-90011-22334",
                    "address": {
                        "street": "17 MG Road, Ernakulam",
                        "city": "Kochi",
                        "state": "Kerala",
                        "zip": "682016"
                    }
                }
            }
        ]

        collection.insert_many(loan_data)
        print(f"Successfully inserted {len(loan_data)} loan records.")

        users_col = db["users_auth"]
        new_users = [
            {"username": "rahul.mehta@example.com",     "email": "rahul.mehta@example.com"},
            {"username": "ananya.k@example.com",         "email": "ananya.k@example.com"},
            {"username": "vikram.r@example.com",         "email": "vikram.r@example.com"},
            {"username": "sneha.gupta@example.com",      "email": "sneha.gupta@example.com"},
            {"username": "arjun.nair@example.com",       "email": "arjun.nair@example.com"},
            {"username": "meera.joshi@example.com",      "email": "meera.joshi@example.com"},
            {"username": "rohan.sharma@example.com",     "email": "rohan.sharma@example.com"},
            {"username": "kavya.menon@example.com",      "email": "kavya.menon@example.com"},
        ]
        import hashlib
        def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()
        for u in new_users:
            if not users_col.find_one({"username": u["username"]}):
                users_col.insert_one({
                    "username": u["username"],
                    "password_hash": hash_pw("user123"),
                    "role": "user"
                })
        print(f"Seeded {len(new_users)} new user accounts.")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    db_initializer()
