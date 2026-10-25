import csv
import glob
import logging
import os
import re
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class FinanceDB:
    """SQLite 기반 고성능 로컬 금융 마스터 데이터베이스 (ACID 및 다년도 초고속 쿼리 지원)"""

    def __init__(self, data_dir: str):
        self.db_path = os.path.join(data_dir, "finance.db")
        os.makedirs(data_dir, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """테이블 및 인덱스 초기화"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            # 1. monthly_bills (월별 청구 및 출금 캘린더)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS monthly_bills (
                id TEXT PRIMARY KEY,
                due_date TEXT,
                billing_month TEXT,
                category TEXT,
                institution TEXT,
                item_name TEXT,
                principal INTEGER DEFAULT 0,
                interest INTEGER DEFAULT 0,
                total_amount INTEGER DEFAULT 0,
                interest_rate TEXT,
                withdrawal_account TEXT,
                status TEXT,
                statement_url TEXT,
                updated_at TEXT
            )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bills_month ON monthly_bills(billing_month)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bills_due ON monthly_bills(due_date)")

            # 2. installments (할부 마스터 원장)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS installments (
                id TEXT PRIMARY KEY,
                card_company TEXT,
                merchant_name TEXT,
                start_date TEXT,
                total_amount INTEGER DEFAULT 0,
                total_rounds INTEGER DEFAULT 1,
                current_round INTEGER DEFAULT 1,
                remaining_rounds INTEGER DEFAULT 0,
                billed_this_month INTEGER DEFAULT 0,
                remaining_principal INTEGER DEFAULT 0,
                status TEXT DEFAULT 'ACTIVE',
                billing_month TEXT,
                updated_at TEXT
            )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_inst_status ON installments(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_inst_month ON installments(billing_month)")

            # 3. transactions (개별 거래 상세 원장 - 수십만 건 누적 가능)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY,
                transaction_date TEXT,
                card_company TEXT,
                card_last4 TEXT,
                merchant_name TEXT,
                category TEXT,
                original_amount INTEGER DEFAULT 0,
                discount_amount INTEGER DEFAULT 0,
                billed_amount INTEGER DEFAULT 0,
                installment_plan TEXT,
                status TEXT DEFAULT 'VERIFIED',
                source TEXT DEFAULT 'MAIL_STATEMENT',
                billing_month TEXT,
                reconciled_at TEXT,
                created_at TEXT
            )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(transaction_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tx_merchant ON transactions(merchant_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tx_month ON transactions(billing_month)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tx_category ON transactions(category)")

            conn.commit()

    def upsert_monthly_bills(self, items: List[Dict[str, Any]]) -> None:
        """monthly_bills 배치 업서트"""
        if not items:
            return
        query = """
        INSERT INTO monthly_bills (
            id, due_date, billing_month, category, institution, item_name,
            principal, interest, total_amount, interest_rate,
            withdrawal_account, status, statement_url, updated_at
        ) VALUES (
            :id, :due_date, :billing_month, :category, :institution, :item_name,
            :principal, :interest, :total_amount, :interest_rate,
            :withdrawal_account, :status, :statement_url, :updated_at
        )
        ON CONFLICT(id) DO UPDATE SET
            due_date = excluded.due_date,
            billing_month = excluded.billing_month,
            category = excluded.category,
            institution = excluded.institution,
            item_name = excluded.item_name,
            principal = excluded.principal,
            interest = excluded.interest,
            total_amount = excluded.total_amount,
            interest_rate = excluded.interest_rate,
            withdrawal_account = excluded.withdrawal_account,
            status = excluded.status,
            statement_url = excluded.statement_url,
            updated_at = excluded.updated_at
        """
        clean_items = []
        for it in items:
            clean_items.append({
                "id": str(it.get("id", "")),
                "due_date": str(it.get("due_date", "")),
                "billing_month": str(it.get("billing_month", "")),
                "category": str(it.get("category", "")),
                "institution": str(it.get("institution", "")),
                "item_name": str(it.get("item_name", "")),
                "principal": int(it.get("principal") or 0),
                "interest": int(it.get("interest") or 0),
                "total_amount": int(it.get("total_amount") or 0),
                "interest_rate": str(it.get("interest_rate") or "-"),
                "withdrawal_account": str(it.get("withdrawal_account") or "우리은행(주거래)"),
                "status": str(it.get("status") or "PENDING"),
                "statement_url": str(it.get("statement_url", "")),
                "updated_at": it.get("updated_at") or datetime.now().isoformat(),
            })

        with self._get_conn() as conn:
            conn.executemany(query, clean_items)
            conn.commit()

    def upsert_installments(self, items: List[Dict[str, Any]]) -> None:
        """installments 배치 업서트"""
        if not items:
            return
        query = """
        INSERT INTO installments (
            id, card_company, merchant_name, start_date, total_amount,
            total_rounds, current_round, remaining_rounds, billed_this_month,
            remaining_principal, status, billing_month, updated_at
        ) VALUES (
            :id, :card_company, :merchant_name, :start_date, :total_amount,
            :total_rounds, :current_round, :remaining_rounds, :billed_this_month,
            :remaining_principal, :status, :billing_month, :updated_at
        )
        ON CONFLICT(id) DO UPDATE SET
            card_company = excluded.card_company,
            merchant_name = excluded.merchant_name,
            start_date = excluded.start_date,
            total_amount = excluded.total_amount,
            total_rounds = excluded.total_rounds,
            current_round = excluded.current_round,
            remaining_rounds = excluded.remaining_rounds,
            billed_this_month = excluded.billed_this_month,
            remaining_principal = excluded.remaining_principal,
            status = excluded.status,
            billing_month = excluded.billing_month,
            updated_at = excluded.updated_at
        """
        clean_items = []
        for it in items:
            clean_items.append({
                "id": str(it.get("id", "")),
                "card_company": str(it.get("card_company", "")),
                "merchant_name": str(it.get("merchant_name", "")),
                "start_date": str(it.get("start_date", "")),
                "total_amount": int(it.get("total_amount") or 0),
                "total_rounds": int(it.get("total_rounds") or 1),
                "current_round": int(it.get("current_round") or 1),
                "remaining_rounds": int(it.get("remaining_rounds") or 0),
                "billed_this_month": int(it.get("billed_this_month") or 0),
                "remaining_principal": int(it.get("remaining_principal") or 0),
                "status": str(it.get("status") or "ACTIVE"),
                "billing_month": str(it.get("billing_month", "")),
                "updated_at": it.get("updated_at") or datetime.now().isoformat(),
            })

        with self._get_conn() as conn:
            conn.executemany(query, clean_items)
            conn.commit()

    def upsert_transactions(self, items: List[Dict[str, Any]]) -> None:
        """transactions 배치 업서트"""
        if not items:
            return
        query = """
        INSERT INTO transactions (
            id, transaction_date, card_company, card_last4, merchant_name,
            category, original_amount, discount_amount, billed_amount,
            installment_plan, status, source, billing_month, reconciled_at, created_at
        ) VALUES (
            :id, :transaction_date, :card_company, :card_last4, :merchant_name,
            :category, :original_amount, :discount_amount, :billed_amount,
            :installment_plan, :status, :source, :billing_month, :reconciled_at, :created_at
        )
        ON CONFLICT(id) DO UPDATE SET
            transaction_date = excluded.transaction_date,
            card_company = excluded.card_company,
            card_last4 = excluded.card_last4,
            merchant_name = excluded.merchant_name,
            category = excluded.category,
            original_amount = excluded.original_amount,
            discount_amount = excluded.discount_amount,
            billed_amount = excluded.billed_amount,
            installment_plan = excluded.installment_plan,
            status = excluded.status,
            source = excluded.source,
            billing_month = excluded.billing_month,
            reconciled_at = excluded.reconciled_at
        """
        now_str = datetime.now().isoformat()
        clean_items = []
        for it in items:
            clean_items.append({
                "id": str(it.get("id", "")),
                "transaction_date": str(it.get("transaction_date", "")),
                "card_company": str(it.get("card_company", "")),
                "card_last4": str(it.get("card_last4", "")),
                "merchant_name": str(it.get("merchant_name", "")),
                "category": str(it.get("category", "일반")),
                "original_amount": int(it.get("original_amount") or 0),
                "discount_amount": int(it.get("discount_amount") or 0),
                "billed_amount": int(it.get("billed_amount") or 0),
                "installment_plan": str(it.get("installment_plan") or "일시불"),
                "status": str(it.get("status") or "VERIFIED"),
                "source": str(it.get("source") or "MAIL_STATEMENT"),
                "billing_month": str(it.get("billing_month", "")),
                "reconciled_at": it.get("reconciled_at") or now_str,
                "created_at": it.get("created_at") or now_str,
            })

        with self._get_conn() as conn:
            conn.executemany(query, clean_items)
            conn.commit()

    def reconcile_and_upsert_transactions(self, statement_items: List[Dict[str, Any]]) -> Dict[str, int]:
        """결산 명세서와 기존 실시간 PENDING(SMS/앱) 거래 간 1:1 대사(Reconciliation) 및 승격"""
        if not statement_items:
            return {"matched": 0, "inserted": 0, "ghost_flagged": 0}

        now_str = datetime.now().isoformat()
        stats = {"matched": 0, "inserted": 0, "ghost_flagged": 0}

        with self._get_conn() as conn:
            cursor = conn.cursor()

            # 1. 기존 PENDING 상태의 실시간 거래 목록 조회
            cursor.execute("""
            SELECT id, transaction_date, card_company, card_last4, merchant_name, original_amount, billed_amount
            FROM transactions
            WHERE status = 'PENDING'
            """)
            pending_rows = [dict(r) for r in cursor.fetchall()]

            consumed_pending_ids = set()
            new_items_to_insert = []

            for s in statement_items:
                s_date = str(s.get("transaction_date", ""))[:10]
                s_card = str(s.get("card_company", ""))
                s_orig_amt = int(s.get("original_amount") or s.get("billed_amount") or 0)
                s_billed_amt = int(s.get("billed_amount") or 0)

                # 2. PENDING 후보군 중 1:1 매칭 탐색 (카드사 일치 & 금액 일치 & 날짜 ±1일 오차)
                matched_id = None
                for p in pending_rows:
                    if p["id"] in consumed_pending_ids:
                        continue
                    if p.get("card_company") != s_card:
                        continue
                    p_orig = int(p.get("original_amount") or p.get("billed_amount") or 0)
                    p_billed = int(p.get("billed_amount") or 0)
                    # 금액 일치 여부 (원금 또는 청구액)
                    if s_orig_amt != p_orig and s_billed_amt != p_billed and s_billed_amt != p_orig:
                        continue

                    # 날짜 ±1일 일치 여부
                    p_date = str(p.get("transaction_date") or "")[:10]
                    date_diff = 999
                    if s_date and p_date:
                        try:
                            d1 = datetime.strptime(s_date, "%Y-%m-%d")
                            d2 = datetime.strptime(p_date, "%Y-%m-%d")
                            date_diff = abs((d1 - d2).days)
                        except Exception:
                            date_diff = 0 if s_date == p_date else 999

                    if date_diff <= 1:
                        matched_id = p["id"]
                        break

                if matched_id:
                    # 매칭 성공: SMS PENDING 건을 확정 데이터로 승격(Promotion)
                    cursor.execute("""
                    UPDATE transactions
                    SET merchant_name = :merchant_name,
                        category = :category,
                        original_amount = :original_amount,
                        discount_amount = :discount_amount,
                        billed_amount = :billed_amount,
                        installment_plan = :installment_plan,
                        status = 'VERIFIED',
                        source = 'RECONCILED',
                        billing_month = :billing_month,
                        reconciled_at = :reconciled_at
                    WHERE id = :id
                    """, {
                        "id": matched_id,
                        "merchant_name": str(s.get("merchant_name", "")),
                        "category": str(s.get("category", "일반")),
                        "original_amount": int(s.get("original_amount") or 0),
                        "discount_amount": int(s.get("discount_amount") or 0),
                        "billed_amount": int(s.get("billed_amount") or 0),
                        "installment_plan": str(s.get("installment_plan") or "일시불"),
                        "billing_month": str(s.get("billing_month", "")),
                        "reconciled_at": now_str,
                    })
                    consumed_pending_ids.add(matched_id)
                    stats["matched"] += 1
                else:
                    # 매칭 실패 (SMS에 없었던 건 - 교통, 연회비, 누락분): 신규 삽입 대상으로 등록
                    new_items_to_insert.append(s)

            conn.commit()

        # 3. 누락된 신규 건(명세서에만 있는 건) 일반 upsert로 삽입 (시간순 자동 정렬 지원)
        if new_items_to_insert:
            self.upsert_transactions(new_items_to_insert)
            stats["inserted"] += len(new_items_to_insert)

        # 4. 결산 마감된 월에 속하면서 끝내 매칭되지 않은 과거 PENDING 건 (유령 중복 / 취소건) 처리
        billing_months = {s.get("billing_month") for s in statement_items if s.get("billing_month")}
        with self._get_conn() as conn:
            cursor = conn.cursor()
            for bm in billing_months:
                if not bm:
                    continue
                cursor.execute("""
                UPDATE transactions
                SET status = 'DUPLICATE_SUSPECT', reconciled_at = ?
                WHERE status = 'PENDING' AND billing_month IS NOT NULL AND billing_month != '' AND billing_month < ?
                """, (now_str, bm))
                stats["ghost_flagged"] += cursor.rowcount
            conn.commit()

        return stats

    def export_yearly_transactions_csv(self, year: str, out_path: str) -> int:
        """특정 연도의 거래 내역을 CSV로 내보내기 (연도별 샤딩 뷰)"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT id, transaction_date, card_company, card_last4, merchant_name,
                   category, original_amount, discount_amount, billed_amount,
                   installment_plan, status, source, billing_month, reconciled_at
            FROM transactions
            WHERE transaction_date LIKE ? OR billing_month LIKE ?
            ORDER BY transaction_date DESC, id DESC
            """, (f"{year}-%", f"{year}-%"))
            rows = [dict(r) for r in cursor.fetchall()]

        headers = [
            "id", "transaction_date", "card_company", "card_last4", "merchant_name",
            "category", "original_amount", "discount_amount", "billed_amount",
            "installment_plan", "status", "source", "billing_month", "reconciled_at"
        ]
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            if rows:
                writer.writerows(rows)
        return len(rows)

    def export_all_yearly_csvs(self, target_dir: str) -> List[str]:
        """모든 연도별 거래원장 CSV 생성 (가족_거래_원장_YYYY.csv)"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT DISTINCT yr FROM (
                SELECT substr(transaction_date, 1, 4) as yr FROM transactions
                UNION
                SELECT substr(billing_month, 1, 4) as yr FROM transactions
            )
            WHERE yr IS NOT NULL AND length(yr) = 4 AND yr GLOB '[0-9][0-9][0-9][0-9]'
            ORDER BY yr DESC
            """)
            years = [r[0] for r in cursor.fetchall()]

        if not years:
            years = [datetime.now().strftime("%Y")]

        exported_files = []
        for y in years:
            p = os.path.join(target_dir, f"가족_거래_원장_{y}.csv")
            self.export_yearly_transactions_csv(y, p)
            exported_files.append(p)
        return exported_files

    def export_installments_csv(self, out_path: str) -> int:
        """현재 최신 청구월 기준 유효 할부 원장 CSV 내보내기"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT id, card_company, merchant_name, start_date, total_amount,
                   total_rounds, current_round, remaining_rounds, billed_this_month,
                   remaining_principal, status, billing_month, updated_at
            FROM installments
            WHERE billing_month = (SELECT MAX(billing_month) FROM installments)
              AND status = 'ACTIVE' AND remaining_rounds > 0 AND total_amount > 0
            ORDER BY remaining_rounds DESC, id ASC
            """)
            rows = [dict(r) for r in cursor.fetchall()]

        headers = [
            "id", "card_company", "merchant_name", "start_date", "total_amount",
            "total_rounds", "current_round", "remaining_rounds", "billed_this_month",
            "remaining_principal", "status", "billing_month", "updated_at"
        ]
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            if rows:
                writer.writerows(rows)
        return len(rows)

    def export_monthly_bills_csv(self, out_path: str) -> int:
        """월별 청구 원장 CSV 내보내기"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT id, due_date, billing_month, category, institution, item_name,
                   principal, interest, total_amount, interest_rate,
                   withdrawal_account, status, statement_url, updated_at
            FROM monthly_bills
            ORDER BY due_date ASC
            """)
            rows = [dict(r) for r in cursor.fetchall()]

        headers = [
            "id", "due_date", "billing_month", "category", "institution", "item_name",
            "principal", "interest", "total_amount", "interest_rate",
            "withdrawal_account", "status", "statement_url", "updated_at"
        ]
        with open(out_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            if rows:
                writer.writerows(rows)
        return len(rows)

    def get_monthly_bills(self, billing_month: Optional[str] = None) -> List[Dict[str, Any]]:
        """월별 청구 목록 조회"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            if billing_month:
                cursor.execute("SELECT * FROM monthly_bills WHERE billing_month = ? ORDER BY due_date ASC", (billing_month,))
            else:
                cursor.execute("SELECT * FROM monthly_bills ORDER BY due_date ASC")
            return [dict(r) for r in cursor.fetchall()]

    def get_active_installments(self) -> List[Dict[str, Any]]:
        """현재 최신 청구월에 진행 중인 유효 잔여 할부 목록 조회"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM installments
            WHERE billing_month = (SELECT MAX(billing_month) FROM installments)
              AND status = 'ACTIVE' AND remaining_rounds > 0 AND total_amount > 0
            ORDER BY remaining_rounds DESC, id ASC
            """)
            return [dict(r) for r in cursor.fetchall()]

    def sync_from_csv_directory(self, finance_dir: str) -> Dict[str, int]:
        """기존 CSV 파일들로부터 SQLite 데이터베이스 초기 적재 및 복원 (Self-healing / Migration)"""
        counts = {"monthly_bills": 0, "installments": 0, "transactions": 0}
        if not os.path.exists(finance_dir):
            return counts

        # 1. 가족_금융_원장.csv
        bills_csv = os.path.join(finance_dir, "가족_금융_원장.csv")
        if os.path.exists(bills_csv):
            try:
                with open(bills_csv, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    self.upsert_monthly_bills(rows)
                    counts["monthly_bills"] = len(rows)
            except Exception as e:
                logger.warning(f"Failed to import {bills_csv}: {e}")

        # 2. 가족_할부_원장.csv
        inst_csv = os.path.join(finance_dir, "가족_할부_원장.csv")
        if os.path.exists(inst_csv):
            try:
                with open(inst_csv, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    self.upsert_installments(rows)
                    counts["installments"] = len(rows)
            except Exception as e:
                logger.warning(f"Failed to import {inst_csv}: {e}")

        # 3. 가족_거래_원장.csv 및 가족_거래_원장_*.csv
        tx_files = glob.glob(os.path.join(finance_dir, "가족_거래_원장*.csv"))
        all_tx_rows = []
        for tf in tx_files:
            try:
                with open(tf, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    all_tx_rows.extend(list(reader))
            except Exception as e:
                logger.warning(f"Failed to import {tf}: {e}")

        if all_tx_rows:
            self.upsert_transactions(all_tx_rows)
            counts["transactions"] = len(all_tx_rows)

        return counts

    def query_spending(
        self,
        keyword: Optional[str] = None,
        year: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """다년도 통합 지출 및 가맹점 검색 (SQLite Full Scan)"""
        conditions = ["1=1"]
        params = []

        if keyword:
            conditions.append("(merchant_name LIKE ? OR category LIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        if year:
            conditions.append("transaction_date LIKE ?")
            params.append(f"{year}-%")
        if category:
            conditions.append("category = ?")
            params.append(category)

        where_clause = " AND ".join(conditions)
        query = f"""
        SELECT id, transaction_date, card_company, merchant_name, category,
               original_amount, discount_amount, billed_amount, installment_plan, status
        FROM transactions
        WHERE {where_clause}
        ORDER BY transaction_date DESC, id DESC
        LIMIT ?
        """
        params.append(limit)

        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]
