import base64
import csv
import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from bs4 import BeautifulSoup
import typer
from rich.console import Console
from rich.table import Table

from core.base import BaseHandler, HandlerResult
from core.config import MailSyncConfig
from core.gog_client import GogClient

logger = logging.getLogger(__name__)

class FinanceHandler(BaseHandler):
    name = "finance"
    description = "우리카드, 현대카드, 삼성카드 명세서 및 우리은행 대출 원리금 통지 수집/복호화/정리"

    def __init__(self):
        pass

    def get_gmail_query(self, time_window_str: Optional[str] = None, month_str: Optional[str] = None) -> str:
        """금융 메일 검색 쿼리: 카드 3사 + 우리은행"""
        query_parts = [
            "(from:samsungcard.com OR from:hyundaicard.com OR from:wooricard.com OR from:wooribank.com)",
            "(명세서 OR 이자납입기일 OR 이용대금 OR 대출금)",
        ]
        if time_window_str:
            query_parts.append(time_window_str)
        return " ".join(query_parts)

    def process(
        self,
        messages: List[Dict[str, Any]],
        config: MailSyncConfig,
        progress_callback: Optional[Callable[[str, Optional[float]], None]] = None,
    ) -> HandlerResult:
        gog = GogClient(account=config.google_account)
        processed_items: List[Dict[str, Any]] = []

        total_msgs = len(messages)
        for idx, msg_meta in enumerate(messages):
            msg_id = msg_meta.get("id") or msg_meta.get("threadId")
            subject = msg_meta.get("subject", "")
            from_addr = msg_meta.get("from", "")

            if progress_callback:
                progress_callback(f"[finance] 메일 상세 조회 중 ({idx+1}/{total_msgs}): {subject[:30]}...", (idx / total_msgs))

            raw_data = gog.get_message_raw(msg_id)
            if not raw_data:
                continue

            # 메일 유형 판별
            item = self._parse_single_email(msg_id, raw_data, config, gog, progress_callback)
            if item:
                processed_items.append(item)

        if progress_callback:
            progress_callback(f"[finance] 데이터 저장 중 (총 {len(processed_items)}건)...", 0.9)

        # 1. Google Sheets 갱신 (raw_ledger)
        self._sync_to_google_sheets(processed_items, config, gog)

        # 2. Obsidian 마크다운 갱신 (가족 금융 대시보드.md)
        self._sync_to_obsidian(processed_items, config)

        return HandlerResult(
            handler_name=self.name,
            success=True,
            processed_count=len(processed_items),
            summary=f"금융 메일 {len(processed_items)}건 처리 완료",
            items=processed_items,
        )

    def _parse_single_email(
        self,
        msg_id: str,
        raw_msg: Dict[str, Any],
        config: MailSyncConfig,
        gog: GogClient,
        progress_callback: Optional[Callable] = None,
    ) -> Optional[Dict[str, Any]]:
        headers = {h.get("name", "").lower(): h.get("value", "") for h in raw_msg.get("payload", {}).get("headers", [])}
        subject = headers.get("subject", "")
        from_hdr = headers.get("from", "")
        date_hdr = headers.get("date", "")

        # A. 우리은행 대출 메일
        if "wooribank.com" in from_hdr or "우리은행" in from_hdr:
            if "이자납입기일" in subject or "대출" in subject:
                return self._parse_woori_loan(msg_id, raw_msg, subject, date_hdr)

        # B. 삼성카드 명세서
        if "samsungcard.com" in from_hdr or "삼성카드" in subject:
            if "명세서" in subject:
                return self._parse_card_statement(
                    msg_id, raw_msg, "삼성카드", "SFC3", 13, subject, config, gog, progress_callback
                )

        # C. 현대카드 명세서
        if "hyundaicard.com" in from_hdr or "현대카드" in subject:
            if "명세서" in subject:
                return self._parse_card_statement(
                    msg_id, raw_msg, "현대카드", "현대카드", 12, subject, config, gog, progress_callback
                )

        # D. 우리카드 명세서
        if "wooricard.com" in from_hdr or "우리카드" in subject:
            if "명세서" in subject:
                return self._parse_card_statement(
                    msg_id, raw_msg, "우리카드", "TEN", 14, subject, config, gog, progress_callback
                )

        return None

    def _get_body_html(self, payload: Dict[str, Any]) -> str:
        if payload.get("mimeType") == "text/html" and payload.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore")
        for p in payload.get("parts", []):
            res = self._get_body_html(p)
            if res:
                return res
        return ""

    def _parse_woori_loan(self, msg_id: str, raw_msg: Dict[str, Any], subject: str, date_hdr: str) -> Dict[str, Any]:
        """우리은행 대출 이자 및 원금 납입 통지 본문 파싱"""
        html = self._get_body_html(raw_msg.get("payload", {}))
        soup = BeautifulSoup(html, "html.parser")

        principal = 0
        interest = 0
        rate = "3.26%"
        due_date_str = ""

        # 테이블에서 원금/이자/이율/납입일 추출
        for tr in soup.find_all("tr"):
            th = tr.find("th")
            td = tr.find("td")
            if th and td:
                key = th.get_text(strip=True)
                val = td.get_text(strip=True)
                if "원금" in key and not "납입일" in key:
                    num_val = re.sub(r"[^\d]", "", val)
                    if num_val:
                        principal = int(num_val)
                elif "이자" in key and not "납입일" in key:
                    num_val = re.sub(r"[^\d]", "", val)
                    if num_val:
                        interest = int(num_val)
                elif "이율" in key or "금리" in key:
                    rate = val
                elif "이자납입일" in key or "원금납입일" in key:
                    due_date_str = val

        # 날짜 포맷 정리 (예: 26년10월15일 -> 2026-10-15)
        now = datetime.now()
        due_date = f"{now.year}-{now.month:02d}-15"
        billing_month = f"{now.year}-{now.month:02d}"

        if due_date_str:
            m = re.search(r"(\d{2,4})[^\d]*(\d{1,2})[^\d]*(\d{1,2})", due_date_str)
            if m:
                y = int(m.group(1))
                if y < 100:
                    y += 2000
                mo = int(m.group(2))
                d = int(m.group(3))
                due_date = f"{y}-{mo:02d}-{d:02d}"
                billing_month = f"{y}-{mo:02d}"

        total_amount = principal + interest
        item_id = f"FIN-{billing_month.replace('-', '')}-WOORI-LOAN"

        return {
            "id": item_id,
            "message_id": msg_id,
            "billing_month": billing_month,
            "due_date": due_date,
            "category": "LOAN",
            "institution": "우리은행",
            "item_name": "일반대출 원리금",
            "principal": principal,
            "interest": interest,
            "total_amount": total_amount,
            "interest_rate": rate,
            "withdrawal_account": "우리은행(주거래)",
            "status": "PENDING",
            "statement_url": "",
            "subject": subject,
            "updated_at": datetime.now().isoformat(),
        }

    def _parse_card_statement(
        self,
        msg_id: str,
        raw_msg: Dict[str, Any],
        institution: str,
        card_name: str,
        default_day: int,
        subject: str,
        config: MailSyncConfig,
        gog: GogClient,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """카드사 보안 HTML 첨부파일 다운로드, 복호화 및 청구금액 추출"""
        now = datetime.now()
        billing_month = f"{now.year}-{now.month:02d}"
        due_date = f"{now.year}-{now.month:02d}-{default_day:02d}"

        # 제목에서 결제일자 추출 (예: 2026년 10월 13일)
        m = re.search(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", subject)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            due_date = f"{y}-{mo:02d}-{d:02d}"
            billing_month = f"{y}-{mo:02d}"

        # 첨부파일 찾기
        attachment_id = None
        attachment_name = "statement.html"
        for part in raw_msg.get("payload", {}).get("parts", []):
            filename = part.get("filename", "")
            if filename.endswith(".html") or filename.endswith(".htm"):
                attachment_id = part.get("body", {}).get("attachmentId")
                attachment_name = filename
                break

        # 파일 저장 경로
        stmt_dir = os.path.join(config.family_finance_dir, "statements", billing_month)
        os.makedirs(stmt_dir, exist_ok=True)
        local_stmt_path = os.path.join(stmt_dir, f"{institution}_{billing_month}.html")

        # 첨부파일 다운로드
        if attachment_id:
            gog.download_attachment(msg_id, attachment_id, local_stmt_path)

        # 복호화 시도
        total_amount = 0
        if os.path.exists(local_stmt_path) and config.birth_date_6digit:
            if progress_callback:
                progress_callback(f"[finance] {institution} 보안 HTML 복호화 시도 중...", None)
            decrypted_amount = self._decrypt_html_and_extract_amount(local_stmt_path, config.birth_date_6digit)
            if decrypted_amount:
                total_amount = decrypted_amount

        item_id = f"FIN-{billing_month.replace('-', '')}-{institution}"
        rel_link = f"statements/{billing_month}/{institution}_{billing_month}.html"

        return {
            "id": item_id,
            "message_id": msg_id,
            "billing_month": billing_month,
            "due_date": due_date,
            "category": "CARD",
            "institution": institution,
            "item_name": f"{institution} {card_name}",
            "principal": total_amount,
            "interest": 0,
            "total_amount": total_amount,
            "interest_rate": "-",
            "withdrawal_account": "우리은행(주거래)",
            "status": "PENDING",
            "statement_url": rel_link,
            "subject": subject,
            "updated_at": datetime.now().isoformat(),
        }

    def _decrypt_html_and_extract_amount(self, html_path: str, password: str) -> Optional[int]:
        """Playwright 헤드리스 브라우저를 통해 보안 HTML 복호화 및 청구금액 추출"""
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()

                # 알림창(alert) 자동 닫기 핸들러
                page.on("dialog", lambda dialog: dialog.dismiss())

                page.goto(f"file://{os.path.abspath(html_path)}", timeout=15000)

                # 1. 패스워드 직접 주입 (현대카드 p2_temp 등 hidden 트릭 우회)
                injected = page.evaluate("""(pw) => {
                    const temp = document.querySelector('input[name="p2_temp"]');
                    if (temp) temp.style.display = 'none';

                    const pwd = document.getElementById('password') || 
                                document.querySelector('input[type="password"]') ||
                                document.decForm?.p2;
                    if (pwd) {
                        pwd.style.display = 'inline-block';
                        pwd.value = pw;
                        return true;
                    }
                    return false;
                }""", password)

                if not injected:
                    browser.close()
                    return None

                # 2. 복호화 실행 함수(doAction 또는 submit) 호출
                page.evaluate("""() => {
                    if (typeof doAction === 'function') {
                        doAction();
                    } else {
                        const confirmBtn = document.getElementById('confirm') || 
                                           document.querySelector('input[type="submit"]') || 
                                           document.querySelector('input[type="image"]');
                        if (confirmBtn) {
                            confirmBtn.click();
                        } else if (document.decForm) {
                            document.decForm.submit();
                        }
                    }
                }""")

                # 렌더링 대기
                page.wait_for_timeout(3500)

                # 3. 모든 프레임(iframe) 및 열린 페이지에서 텍스트 수집
                all_text = page.inner_text("body")
                for frame in page.frames:
                    try:
                        all_text += "\n" + frame.inner_text("body")
                    except Exception:
                        pass
                for p_extra in context.pages:
                    try:
                        all_text += "\n" + p_extra.inner_text("body")
                    except Exception:
                        pass

                # 4. 금액 정규식 탐색
                patterns = [
                    r"(?:청구금액|결제예정금액|총\s*결제금액|이번달\s*청구금액|결제금액|이용대금)[^\d]{1,25}([\d,]{3,12})\s*원",
                    r"([\d,]{3,12})\s*원\s*(?:결제예정|청구)",
                ]

                clean_num = None
                for pat in patterns:
                    matches = re.findall(pat, all_text)
                    if matches:
                        cand = int(re.sub(r"[^\d]", "", matches[0]))
                        if cand > 0:
                            clean_num = cand
                            break

                browser.close()
                return clean_num
        except Exception as e:
            logger.warning(f"Decryption attempt failed for {html_path}: {e}")
        return None

    def _sync_to_google_sheets(self, items: List[Dict[str, Any]], config: MailSyncConfig, gog: GogClient) -> None:
        """구글 스프레드시트 및 로컬 CSV 원장(raw_ledger) 행 추가 및 갱신"""
        import csv

        # 1. 로컬 CSV 파일 (외부 앱 연동 및 Google Drive 자동 동기화용 단일 정규화 원장)
        csv_path = os.path.join(config.family_finance_dir, f"{config.spreadsheet_name}.csv")
        headers = [
            "id", "due_date", "billing_month", "category", "institution",
            "item_name", "principal", "interest", "total_amount", "interest_rate",
            "withdrawal_account", "status", "statement_url", "updated_at"
        ]

        existing_rows_dict: Dict[str, Dict[str, Any]] = {}
        if os.path.exists(csv_path):
            try:
                with open(csv_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        if r.get("id"):
                            existing_rows_dict[r["id"]] = r
            except Exception as e:
                logger.warning(f"Failed to read existing CSV {csv_path}: {e}")

        # 신규 아이템 병합
        for item in items:
            item_id = item.get("id")
            if item_id:
                existing_rows_dict[item_id] = {h: item.get(h, "") for h in headers}

        # CSV 파일 다시 쓰기 (정렬: due_date 오름차순)
        sorted_csv_items = sorted(existing_rows_dict.values(), key=lambda x: str(x.get("due_date", "")))
        try:
            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                writer.writerows(sorted_csv_items)
        except Exception as e:
            logger.warning(f"Failed to write CSV {csv_path}: {e}")

        # 2. 구글 스프레드시트 API 연동 (사용 가능한 경우 보조 동기화)
        try:
            sheet_id = gog.ensure_spreadsheet(config.spreadsheet_name, config.gog_family_folder_id, default_sheet="raw_ledger")
            if sheet_id:
                existing_rows = gog.get_sheet_values(sheet_id, "raw_ledger!A1:N1")
                if not existing_rows or not existing_rows[0]:
                    gog.append_sheet_row(sheet_id, "raw_ledger", headers)

                for item in items:
                    row = [item.get(h, "") for h in headers]
                    gog.append_sheet_row(sheet_id, "raw_ledger", row)
        except Exception as e:
            logger.info(f"Google Sheets API sync skipped (fallback to CSV ledger): {e}")

    def _sync_to_obsidian(self, items: List[Dict[str, Any]], config: MailSyncConfig) -> None:
        """옵시디언 areas/family/finance/가족 금융 대시보드.md 스마트 갱신 (전체 원장 기반 최신화)"""
        if not config.is_local_vault:
            return

        dashboard_path = os.path.join(config.family_finance_dir, "가족 금융 대시보드.md")
        csv_path = os.path.join(config.family_finance_dir, f"{config.spreadsheet_name}.csv")
        now_str = datetime.now().strftime("%Y-%m-%d")

        # 전체 원장 CSV 로드 (이전 이력과 병합된 상태 보장)
        all_items: List[Dict[str, Any]] = []
        if os.path.exists(csv_path):
            try:
                with open(csv_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        # 숫자형 필드 변환
                        r["principal"] = int(r.get("principal") or 0)
                        r["interest"] = int(r.get("interest") or 0)
                        r["total_amount"] = int(r.get("total_amount") or 0)
                        all_items.append(r)
            except Exception as e:
                logger.error(f"Failed to read CSV for dashboard sync: {e}")

        if not all_items:
            all_items = items

        if not all_items:
            return

        # 최신 청구월 도출 (예: 2026-10)
        billing_months = sorted(list({it.get("billing_month", "") for it in all_items if it.get("billing_month")}))
        latest_month = billing_months[-1] if billing_months else datetime.now().strftime("%Y-%m")

        # 이번 달 아이템과 과거 아이템 분리
        current_month_items = sorted(
            [it for it in all_items if it.get("billing_month") == latest_month],
            key=lambda x: x.get("due_date", "")
        )
        current_month_total = sum(it.get("total_amount", 0) for it in current_month_items)

        # 이번 달 요약 마크다운 렌더링
        lines = [
            "---",
            "type: dashboard",
            "title: '가족 금융 및 결제 대시보드'",
            "tags:",
            "  - 금융",
            "  - 대시보드",
            "  - 가계부",
            "  - 가족자산",
            f"updated: {now_str}",
            "---",
            "",
            "# 💳 우리 가족 금융 및 결제 대시보드",
            "",
            f"> [!INFO] 📊 **{latest_month}월 결제 및 상환 종합 KPI 요약**",
            f"> - **이번 달 총 출금 소요액**: **{current_month_total:,}원**",
            "> - **주요 출금 집중 기간**: **매월 12일 ~ 15일 (4일 연속 집중 출금)**",
            "> - **주요 출금 통장**: **우리은행(주거래 통장)**",
            f"> - **데이터 원본 스프레드시트**: [[{config.spreadsheet_name}.csv|{config.spreadsheet_name} (CSV 원장)]]",
            "",
            "---",
            "",
            f"## 📅 이번 달 결제 캘린더 ({latest_month}, 12~15일 타임라인)",
            "",
            "| 결제일 | 구분 | 금융기관 | 항목명 | 금액(원) | 적용이율 | 출금계좌 | 상태 | 명세서 |",
            "| :--- | :--- | :--- | :--- | :---: | :---: | :--- | :---: | :---: |",
        ]

        for it in current_month_items:
            amt_str = f"{it.get('total_amount', 0):,}원"
            link = f"[[{it.get('statement_url')}]]" if it.get("statement_url") else "-"
            lines.append(
                f"| **{it.get('due_date')}** | {it.get('category')} | **{it.get('institution')}** | {it.get('item_name')} | **{amt_str}** | {it.get('interest_rate') or '-'} | {it.get('withdrawal_account')} | {it.get('status')} | {link} |"
            )

        lines.extend([
            "",
            "---",
            "",
            "## 🏦 우리은행 대출 상환 관리 현황",
            "",
        ])

        # 대출 항목 브리핑 (최신 내역 우선)
        loan_items = [it for it in current_month_items if it.get("category") == "LOAN"]
        if not loan_items:
            loan_items = [it for it in all_items if it.get("category") == "LOAN"]

        if loan_items:
            loan = loan_items[-1]
            lines.extend([
                f"> [!NOTE] 📈 **우리은행 일반대출 금리 및 원리금 현황** ({loan.get('billing_month')} 기준)",
                f"> - **적용 금리**: **{loan.get('interest_rate')}**",
                f"> - **월 상환 원금**: **{loan.get('principal', 0):,}원**",
                f"> - **월 납입 이자**: **{loan.get('interest', 0):,}원**",
                f"> - **월 총 상환액**: **{loan.get('total_amount', 0):,}원** (매월 15일 자동이체)",
                "",
            ])
        else:
            lines.append("> *수신된 대출 통지 내역이 없습니다.*")

        # 과거 월별 이력 요약 테이블 (역순)
        lines.extend([
            "---",
            "",
            "## 📜 월별 결제 이력 요약 (최근순)",
            "",
            "| 청구월 | 현대카드 | 삼성카드 | 우리카드 | 우리은행 대출 | 월 총 결제액 |",
            "| :---: | :---: | :---: | :---: | :---: | :---: |",
        ])

        month_map: Dict[str, Dict[str, int]] = {}
        for it in all_items:
            m = it.get("billing_month")
            if not m:
                continue
            if m not in month_map:
                month_map[m] = {"현대카드": 0, "삼성카드": 0, "우리카드": 0, "우리은행": 0, "total": 0}
            inst = it.get("institution", "")
            amt = it.get("total_amount", 0)
            if inst in month_map[m]:
                month_map[m][inst] += amt
            month_map[m]["total"] += amt

        for m in sorted(month_map.keys(), reverse=True):
            data = month_map[m]
            h_str = f"{data['현대카드']:,}원" if data['현대카드'] > 0 else "-"
            s_str = f"{data['삼성카드']:,}원" if data['삼성카드'] > 0 else "-"
            w_str = f"{data['우리카드']:,}원" if data['우리카드'] > 0 else "-"
            l_str = f"{data['우리은행']:,}원" if data['우리은행'] > 0 else "-"
            tot_str = f"**{data['total']:,}원**"
            lines.append(f"| **{m}** | {h_str} | {s_str} | {w_str} | {l_str} | {tot_str} |")

        lines.extend([
            "",
            "---",
            "",
            "## 🔗 가족 허브 바로가기",
            "- 👨‍👩‍👦 [[가족 공통 홈]] (`areas/family/가족 공통 홈.md`)",
            "- 🛡️ [[가족 보험 대시보드]] (`areas/family/가족 보험 대시보드.md`)",
            "- 🔄 [[areas/family/subscription/|가족 정기 구독 서비스]]",
        ])

        with open(dashboard_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        # 가족 공통 홈.md 에 대시보드 링크 연결 보장
        self._ensure_family_home_link(config)

    def _ensure_family_home_link(self, config: MailSyncConfig) -> None:
        """가족 공통 홈.md에 [[가족 금융 대시보드]] 링크 추가"""
        home_path = os.path.join(os.path.dirname(config.family_finance_dir), "가족 공통 홈.md")
        if not os.path.exists(home_path):
            return

        with open(home_path, "r", encoding="utf-8") as f:
            content = f.read()

        if "가족 금융 대시보드" not in content:
            section_to_insert = "## 💳 가족 금융 및 정기 결제 관리\n- 📊 [[가족 금융 대시보드]] (카드 3사 청구액 및 대출 원리금 12~15일 타임라인)\n\n"
            if "## 🛡️ 가족 통합 보험 관제" in content:
                content = content.replace("## 🛡️ 가족 통합 보험 관제", f"{section_to_insert}## 🛡️ 가족 통합 보험 관제")
            else:
                content += f"\n\n{section_to_insert}"

            with open(home_path, "w", encoding="utf-8") as f:
                f.write(content)

    def register_cli(self, sub_app: typer.Typer) -> None:
        """finance 핸들러 전용 서브커맨드 등록"""
        @sub_app.command("calendar")
        def show_calendar(
            month: Optional[str] = typer.Option(None, "--month", "-m", help="조회할 청구월 (예: 2026-10)")
        ):
            """지정/최신 청구월의 12~15일 결제 일정 및 통장별 필요 잔고 브리핑"""
            import csv
            from core.config import load_config
            cfg = load_config()
            console = Console()

            csv_path = os.path.join(cfg.family_finance_dir, f"{cfg.spreadsheet_name}.csv")
            if not os.path.exists(csv_path):
                console.print("[yellow]아직 동기화된 금융 원장(CSV) 파일이 없습니다. 먼저 'mail-sync run'을 실행해 주세요.[/yellow]")
                return

            all_items = []
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    r["total_amount"] = int(r.get("total_amount") or 0)
                    r["principal"] = int(r.get("principal") or 0)
                    r["interest"] = int(r.get("interest") or 0)
                    all_items.append(r)

            if not all_items:
                console.print("[yellow]원장 파일에 기록된 데이터가 없습니다.[/yellow]")
                return

            billing_months = sorted(list({it.get("billing_month", "") for it in all_items if it.get("billing_month")}))
            target_month = month or (billing_months[-1] if billing_months else datetime.now().strftime("%Y-%m"))

            month_items = sorted(
                [it for it in all_items if it.get("billing_month") == target_month],
                key=lambda x: x.get("due_date", "")
            )

            if not month_items:
                console.print(f"[yellow]{target_month}에 해당하는 결제 내역이 없습니다.[/yellow]")
                return

            total_sum = sum(it.get("total_amount", 0) for it in month_items)

            console.print(f"\n[bold cyan]📅 {target_month} 가족 금융 결제 캘린더 (12~15일 집중 출금)[/bold cyan]\n")

            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("결제일", style="bold yellow")
            table.add_column("구분")
            table.add_column("금융기관", style="bold green")
            table.add_column("항목명")
            table.add_column("금액", justify="right", style="bold red")
            table.add_column("이율/비고")
            table.add_column("출금계좌", style="cyan")

            for it in month_items:
                extra = it.get("interest_rate") if it.get("category") == "LOAN" else "-"
                table.add_row(
                    it.get("due_date", ""),
                    it.get("category", ""),
                    it.get("institution", ""),
                    it.get("item_name", ""),
                    f"{it.get('total_amount', 0):,}원",
                    extra,
                    it.get("withdrawal_account", ""),
                )

            console.print(table)
            console.print(f"\n[bold green]💰 {target_month}월 총 필요 출금액: {total_sum:,}원 (우리은행 주거래 계좌)[/bold green]\n")
            console.print("[dim]ℹ️ 자세한 내역은 Obsidian [[가족 금융 대시보드]] 또는 [[가족_금융_원장.csv]]를 확인하세요.[/dim]\n")
