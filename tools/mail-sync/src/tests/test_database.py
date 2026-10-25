import os
import tempfile
import pytest
from core.database import FinanceDB

@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = FinanceDB(tmpdir)
        yield db, tmpdir

def test_db_init_and_tables(temp_db):
    db, tmpdir = temp_db
    assert os.path.exists(os.path.join(tmpdir, "finance.db"))
    with db._get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row["name"] for row in cursor.fetchall()]
        assert "monthly_bills" in tables
        assert "installments" in tables
        assert "transactions" in tables

def test_upsert_and_query_transactions(temp_db):
    db, _ = temp_db
    txs = [
        {
            "id": "TX-001",
            "transaction_date": "2026-10-12",
            "card_company": "현대카드",
            "merchant_name": "스타벅스 위례점",
            "category": "식음료",
            "billed_amount": 6500,
            "installment_plan": "일시불",
        },
        {
            "id": "TX-002",
            "transaction_date": "2026-09-01",
            "card_company": "삼성카드",
            "merchant_name": "쿠팡",
            "category": "쇼핑",
            "billed_amount": 19800,
            "installment_plan": "일시불",
        },
        {
            "id": "TX-003",
            "transaction_date": "2025-11-20",
            "card_company": "우리카드",
            "merchant_name": "쿠팡이츠",
            "category": "식음료",
            "billed_amount": 25000,
            "installment_plan": "일시불",
        },
    ]
    db.upsert_transactions(txs)

    # 1. Keyword search
    res = db.query_spending(keyword="쿠팡")
    assert len(res) == 2

    # 2. Year filter
    res_2026 = db.query_spending(year="2026")
    assert len(res_2026) == 2

    res_2025 = db.query_spending(year="2025")
    assert len(res_2025) == 1
    assert res_2025[0]["id"] == "TX-003"

    # 3. Category filter
    res_food = db.query_spending(category="식음료")
    assert len(res_food) == 2

def test_export_yearly_csvs(temp_db):
    db, tmpdir = temp_db
    txs = [
        {"id": "T1", "transaction_date": "2026-05-10", "merchant_name": "상점A", "billed_amount": 1000},
        {"id": "T2", "transaction_date": "2025-08-15", "merchant_name": "상점B", "billed_amount": 2000},
    ]
    db.upsert_transactions(txs)

    export_dir = os.path.join(tmpdir, "exports")
    os.makedirs(export_dir, exist_ok=True)
    files = db.export_all_yearly_csvs(export_dir)

    assert len(files) == 2
    assert os.path.exists(os.path.join(export_dir, "가족_거래_원장_2026.csv"))
    assert os.path.exists(os.path.join(export_dir, "가족_거래_원장_2025.csv"))

def test_sync_from_csv_directory(temp_db):
    db, tmpdir = temp_db
    csv_dir = os.path.join(tmpdir, "csv_in")
    os.makedirs(csv_dir, exist_ok=True)

    # Write a test transactions CSV
    tx_csv = os.path.join(csv_dir, "가족_거래_원장_2026.csv")
    with open(tx_csv, "w", encoding="utf-8") as f:
        f.write("id,transaction_date,card_company,merchant_name,billed_amount\n")
        f.write("CSV-001,2026-10-01,삼성카드,테스트가맹점,50000\n")

    counts = db.sync_from_csv_directory(csv_dir)
    assert counts["transactions"] == 1

    queried = db.query_spending(keyword="테스트가맹점")
    assert len(queried) == 1
    assert queried[0]["billed_amount"] == 50000
