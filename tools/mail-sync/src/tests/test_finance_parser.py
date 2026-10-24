import base64
import pytest
from handlers.finance import FinanceHandler

SAMPLE_WOORI_HTML = """
<table>
  <tr><th>원금</th><td>769,450</td></tr>
  <tr><th>이자</th><td>589,479</td></tr>
  <tr><th>이율</th><td>3.26%</td></tr>
  <tr><th>이자납입일</th><td>26년10월15일</td></tr>
</table>
"""

def test_woori_loan_parser():
    handler = FinanceHandler()
    b64_data = base64.b64encode(SAMPLE_WOORI_HTML.encode("utf-8")).decode("utf-8")
    raw_msg = {
        "payload": {
            "mimeType": "text/html",
            "body": {"data": ""},
            "headers": [
                {"name": "Subject", "value": "[우리은행]이자납입기일 및 납입금액 안내"},
                {"name": "From", "value": "webmaster@wooribank.com"},
            ],
            "parts": [
                {
                    "mimeType": "text/html",
                    "body": {
                        "data": b64_data
                    }
                }
            ]
        }
    }

    item = handler._parse_woori_loan("msg-test-1", raw_msg, "[우리은행]이자납입기일 및 납입금액 안내", "")
    assert item is not None
    assert item["institution"] == "우리은행"
    assert item["category"] == "LOAN"
    assert item["principal"] == 769450
    assert item["interest"] == 589479
    assert item["total_amount"] == 769450 + 589479
    assert item["interest_rate"] == "3.26%"
    assert item["due_date"] == "2026-10-15"
