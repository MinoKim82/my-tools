/**
 * 가족 금융 통합 원장 - 가계부 모바일 앱 연동용 Google Apps Script (GAS) Webhook
 * 
 * [배포 및 사용 방법]
 * 1. Google Drive의 '가족_금융_원장' 스프레드시트를 엽니다.
 * 2. 상단 메뉴 [확장 프로그램] > [Apps Script] 클릭.
 * 3. 기존 코드를 모두 지우고 본 스크립트 전체를 붙여넣습니다.
 * 4. 우측 상단 [배포] > [새 배포] 클릭:
 *    - 유형 선택: '웹 앱(Web App)'
 *    - 설명: 'Family Finance Mobile Ingestion'
 *    - 다음 사용자 권한으로 실행: '나(내 Google 계정)'
 *    - 액세스 권한: '모든 사용자(Anyone)'
 * 5. 생성된 '웹 앱 URL'(https://script.google.com/macros/s/.../exec)을 복사하여 모바일 앱에 등록합니다.
 * 
 * [모바일 앱 HTTP POST 요청 포맷]
 * POST https://script.google.com/macros/s/.../exec
 * Content-Type: application/json
 * 
 * {
 *   "token": "가족_금융_시크릿키_설정",
 *   "action": "transaction",
 *   "data": {
 *     "date": "2026-10-25 14:30:00",
 *     "card_company": "삼성카드",
 *     "card_last4": "8939",
 *     "merchant_name": "스타벅스",
 *     "amount": 5500,
 *     "installment_plan": 1,
 *     "category": "식음료"
 *   }
 * }
 */

const SECRET_TOKEN = "FAMILY_FINANCE_SECRET_KEY"; // 앱과 공유할 간이 인증 토큰

function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return jsonResponse({ status: "error", message: "Empty body" }, 400);
    }

    const payload = JSON.parse(e.postData.contents);
    if (payload.token !== SECRET_TOKEN) {
      return jsonResponse({ status: "error", message: "Unauthorized token" }, 403);
    }

    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const action = payload.action || "transaction";
    const data = payload.data || {};

    if (action === "transaction") {
      return handleTransaction(ss, data);
    } else if (action === "installment") {
      return handleInstallment(ss, data);
    } else {
      return jsonResponse({ status: "error", message: "Unknown action" }, 400);
    }

  } catch (err) {
    return jsonResponse({ status: "error", message: err.toString() }, 500);
  }
}

function handleTransaction(ss, data) {
  const now = new Date();
  const dateStr = data.date || Utilities.formatDate(now, "Asia/Seoul", "yyyy-MM-dd HH:mm:ss");
  const year = dateStr.slice(0, 4);
  const sheetName = "transactions_" + year;
  let sheet = ss.getSheetByName(sheetName);
  if (!sheet) {
    sheet = ss.insertSheet(sheetName);
    sheet.appendRow([
      "id", "transaction_date", "card_company", "card_last4", "merchant_name",
      "category", "original_amount", "discount_amount", "billed_amount",
      "installment_plan", "status", "source", "billing_month", "reconciled_at"
    ]);
  }

  const trxId = "APP-" + Utilities.formatDate(now, "Asia/Seoul", "yyyyMMdd-HHmmss-") + Math.floor(Math.random() * 1000);
  const amount = Number(data.amount || 0);
  const plan = Number(data.installment_plan || 1);
  const billingMonth = dateStr.slice(0, 7);

  sheet.appendRow([
    trxId,
    dateStr,
    data.card_company || "",
    data.card_last4 || "",
    data.merchant_name || "",
    data.category || "미분류",
    amount,
    0, // discount_amount (초기값 0, 메일 대사 시 업데이트)
    amount, // billed_amount (초기값)
    plan === 1 ? "일시불" : (plan + "개월"),
    "PENDING", // 초기 상태: 가승인/문자수신
    "APP_SMS",
    billingMonth,
    ""
  ]);

  // 할부(2개월 이상)일 경우 installments 시트에도 마스터 자동 등록
  if (plan > 1) {
    handleInstallment(ss, {
      card_company: data.card_company,
      merchant_name: data.merchant_name,
      start_date: dateStr.split(" ")[0],
      total_amount: amount,
      total_rounds: plan,
      current_round: 1,
      billed_this_month: Math.round(amount / plan),
      remaining_principal: amount
    });
  }

  return jsonResponse({ status: "ok", id: trxId });
}

function handleInstallment(ss, data) {
  let sheet = ss.getSheetByName("installments");
  if (!sheet) {
    sheet = ss.insertSheet("installments");
    sheet.appendRow([
      "id", "card_company", "merchant_name", "start_date", "total_amount",
      "total_rounds", "current_round", "remaining_rounds", "billed_this_month",
      "remaining_principal", "status", "updated_at"
    ]);
  }

  const now = new Date();
  const insId = "INS-" + Utilities.formatDate(now, "Asia/Seoul", "yyyyMM-") + (data.merchant_name || "").replace(/\s+/g, "") + "-" + (data.total_rounds || "") + "M";
  const totalRounds = Number(data.total_rounds || 1);
  const currentRound = Number(data.current_round || 1);
  const remainingRounds = Math.max(0, totalRounds - currentRound);

  sheet.appendRow([
    insId,
    data.card_company || "",
    data.merchant_name || "",
    data.start_date || Utilities.formatDate(now, "Asia/Seoul", "yyyy-MM-dd"),
    Number(data.total_amount || 0),
    totalRounds,
    currentRound,
    remainingRounds,
    Number(data.billed_this_month || 0),
    Number(data.remaining_principal || 0),
    "ACTIVE",
    Utilities.formatDate(now, "Asia/Seoul", "yyyy-MM-dd'T'HH:mm:ss")
  ]);

  return jsonResponse({ status: "ok", id: insId });
}

function jsonResponse(obj, code) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function doGet(e) {
  return jsonResponse({ status: "ok", message: "Family Finance Ingestion Webhook is active." }, 200);
}
