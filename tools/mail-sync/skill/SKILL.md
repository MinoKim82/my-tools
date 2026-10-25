---
name: mail-sync
description: Automatically sync, decrypt, and inspect credit card statements (Woori, Hyundai, Samsung) and bank loan payments (Woori Bank) from Gmail into Google Drive, Obsidian family finance dashboard, and 3-tier CSV ledgers using the mail-sync CLI tool. Trigger this skill whenever the user asks about card bills, loan payments, payment calendar, cash flow, installments and remaining months, or mail syncing (e.g., "이번 달 카드값 얼마 나와?", "12~15일에 통장에 얼마 준비해야 돼?", "통장별로 얼마씩 넣어야 해?", "할부 얼마나 남았어?", "카드 할부 내역 보여줘", "남은 할부 개월수 확인해줘", "우리은행 대출 이자 얼마야?", "메일에서 카드 명세서 가져와줘", "금융 대시보드 최신화해줘", "mail-sync 실행해줘", "카드값 결제 일정 보여줘", "금융 원장 데이터 뽑아줘").
---

# mail-sync

`mail-sync`는 Gmail의 금융 메일(우리카드, 현대카드, 삼성카드, 우리은행 대출)을 수집하여 보안 첨부파일을 복호화하고, Google Drive의 Obsidian 볼트(`areas/family/finance/`)에 월간 결제 캘린더 및 CSV 원장으로 자동 동기화하는 도구입니다.

---

## 🚀 빠른 질의 및 실행 절차

### 1. 이번 달 결제 일정 및 카드값/대출 조회
사용자가 이번 달 카드값이나 결제 일정, 통장 잔고 필요액을 물어볼 때 실행합니다:
```bash
mail-sync finance calendar
```
* **출력**: 12일(현대) ➔ 13일(삼성) ➔ 14일(우리) ➔ 15일(우리은행 대출) 일자순 테이블 및 실제 출금 통장별(새마을금고, 토스뱅크, 우리은행) 필요액.

### 2. 진행 중인 카드 할부 잔여 개월 및 부채 현황 조회
사용자가 할부 내역, 남은 개월수, 잔여 할부금 등을 물어볼 때 실행합니다:
```bash
mail-sync finance installments
```
* **출력**: 가맹점별 총 할부원금, 진행 회차, 남은 개월수, 이번달 청구액, 남은 잔여원금 표 및 총 할부 부채.

### 3. 최신 메일 동기화 실행 (수동 동기화 요청 시)
사용자가 "메일 최신화해줘", "새로 온 카드 명세서 가져와"라고 요청할 때:
```bash
# 기본: 최근 1일치 빠른 점검
mail-sync run

# 최근 7일치 점검 필요 시
mail-sync run --days 7

# 특정 월 전체 점검 필요 시
mail-sync run --month 2026-10
```

### 3. 정규화된 금융 원장 데이터 내보내기 (JSON)
사용자 또는 연동 프로그램이 데이터를 요청할 때:
```bash
mail-sync export --json
```

### 4. 동기화 상태 점검
동기화 통계 및 마지막 실행 시각 점검:
```bash
mail-sync status
```

---

## 📊 결과 브리핑 가이드라인

* **결제 일정 안내 시**:
  1. **이번 달 총 출금 소요액**: `₩X,XXX,XXX원`
  2. **12~15일 순차 출금 타임라인**:
     * **12일**: 현대카드 (₩XXX,XXX)
     * **13일**: 삼성카드 (₩XXX,XXX)
     * **14일**: 우리카드 (₩XXX,XXX)
     * **15일**: 우리은행 대출 원리금 (₩1,358,929 / 금리 3.26%, 원금 76.9만 + 이자 58.9만)
  3. **준비 사항**: 주거래 통장(우리은행)에 12일 이전까지 필요 자금 이체 안내.
  4. **파일 링크**: Obsidian [[가족 금융 대시보드]] 링크 제공.

---

## 🛠️ 트러블슈팅

* **카드 금액이 0원으로 표시될 때**:
  * 카드사 보안 HTML은 생년월일 6자리가 필요합니다.
  * `tools/mail-sync/src/.env` 파일의 `BIRTH_DATE_6DIGIT`가 올바르게 설정되어 있는지 확인하세요.
* **Google 인증 실패 시**:
  * 터미널에서 `gog auth list`로 계정 인증 상태를 확인하고 필요 시 `gog auth add minokim82@gmail.com`을 안내하세요.
