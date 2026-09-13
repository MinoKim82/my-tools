---
name: naver-point
description: Automatically collect Naver Pay benefit points and draw campaign random cards using the naver-point CLI tool. Trigger this skill whenever the user mentions collecting Naver points, harvesting Naver Pay benefits, drawing random cards, or asks to run the Naver point script (e.g., "네이버 포인트 뽑아줘", "네이버 포인트 적립해줘", "네이버 페이 혜택 수집해줘", "네이버 카드 뽑기 실행해", "네이버 포인트 모아줘").
---

# Naver Point Picker Skill

네이버페이(Naver Pay) 혜택 페이지의 적립 포인트 버튼을 자동으로 클릭하고, 캠페인 페이지의 랜덤 포인트 카드를 순차적으로 뽑아 네이버 포인트를 수집합니다.

---

## 📋 1. Prerequisites (사전 조건)

1. **로그인 세션**:
   - `naver-point login`을 통해 최초 1회 로그인이 완료되었거나, Google Drive(`my-tools/naver-point/naver_point_session.json`)를 통해 세션이 동기화되어 있어야 합니다.
   - 세션이 만료된 경우 `status`가 `"SessionExpired"`로 반환되며, 사용자에게 터미널에서 `naver-point login`을 실행하도록 안내해야 합니다.
2. **도구 등록 상태**:
   - CLI 도구(`~/.local/bin/naver-point`)가 등록되어 있거나, `tools/naver-point/src/naver-point.sh`를 실행할 수 있는 환경이어야 합니다.

---

## 🚀 2. Execution (실행 절차)

AI 에이전트는 기계 판독을 위해 반드시 `--json` 플래그와 백그라운드 구동을 위한 `--headless` 플래그를 함께 지정하여 실행합니다:

```bash
# 기본 전체 실행 (혜택 수집 + 랜덤 뽑기)
naver-point run --headless --json
```

### 선택 실행 옵션
사용자가 특정 작업만 요청한 경우 해당 플래그를 조합합니다:
- **혜택 포인트만 수집 요청 시**:
  ```bash
  naver-point run --headless --json --benefit-only
  ```
- **랜덤 카드 뽑기만 요청 시**:
  ```bash
  naver-point run --headless --json --draw-only
  ```
- **포인트 잔액만 조회 요청 시**:
  ```bash
  naver-point balance --json
  ```
- **세션 상태만 점검 요청 시**:
  ```bash
  naver-point status --json
  ```
- **세션 초기화/로그아웃 요청 시**:
  ```bash
  naver-point logout --json
  ```
- **Google Drive 세션 동기화 요청 시**:
  ```bash
  naver-point sync pull --json
  ```

> [!TIP]
> 만약 `naver-point` 명령어가 PATH에 없다면 도구 디렉토리 내의 래퍼 스크립트를 직접 호출할 수 있습니다:
> `tools/naver-point/src/naver-point.sh run --headless --json`

---

## 📊 3. Output Specification & Agent Reporting (출력 규격 및 보고 지침)

### 표준 출력 규격 (stdout JSON)
- **수집 성공 시 (`status: Success`)**:
  ```json
  {
    "status": "Success",
    "benefit_clicked": 4,
    "random_draws": 2,
    "starting_balance": 14200,
    "ending_balance": 14225,
    "earned_points": 25,
    "session_synced": true
  }
  ```
- **잔액 조회 성공 시 (`status: Success`)**:
  ```json
  {
    "status": "Success",
    "balance": 14225
  }
  ```
- **세션 만료 시 (`status: SessionExpired`)**:
  ```json
  {
    "status": "SessionExpired",
    "error_message": "네이버 로그인 세션이 만료되었습니다. 'naver-point login'을 실행해 주세요."
  }
  ```
- **실패 시 (`status: Fail`)**:
  ```json
  {
    "status": "Fail",
    "error_message": "Network timeout while loading campaign page",
    "screenshot_path": "logs/error_screenshot.png"
  }
  ```

### 에이전트 응답 보고 가이드라인
- `status`가 `"Success"`인 경우:
  - 수집된 혜택 수(`benefit_clicked`), 카드 뽑기 횟수(`random_draws`), 실제 적립된 포인트(`earned_points`) 및 최종 잔액(`ending_balance`)을 명확히 요약하여 보고합니다.
  - *예시: "네이버 포인트 수집 완료! 혜택 4건 클릭 및 카드 2회 뽑기를 통해 총 25원이 적립되었습니다. (현재 잔액: 14,225원)"*
- `status`가 `"SessionExpired"`인 경우:
  - 사용자에게 세션이 만료되었음을 알리고, 터미널에서 `naver-point login` 명령어를 실행하여 브라우저 창에서 로그인해 줄 것을 정중히 안내합니다.
- `status`가 `"Fail"`인 경우:
  - `error_message`와 함께 에러 캡처 화면(`screenshot_path`)이 보존되었음을 알리고, 재시도 또는 상태 점검(`naver-point status`)을 제안합니다.
