---
name: health-sync
description: Automatically sync Health Sync fitness activities (running, swimming, walking, cycling) to Obsidian vault notes and GPX routes using the health-sync CLI tool. Trigger this skill whenever the user mentions syncing health data, workout logs, running notes, or swimming logs to Obsidian (e.g., "헬스 데이터 동기화해줘", "오늘 운동한 거 옵시디언에 넣어줘", "러닝 기록 동기화해", "수영 일지 가져와", "운동 데이터 최신화해줘", "health-sync 실행해줘").
---

# 🏃 Health Sync to Obsidian 자동 동기화 가이드 (SKILL.md)

이 문서는 AI 에이전트가 `health-sync` 도구를 사용하여 Health Sync 활동 데이터를 스캔하고 Obsidian 볼트에 마크다운 노트와 GPX 자산으로 자동 동기화하는 실행 절차를 정의합니다.

---

## 1. 🚀 실행 명령어 및 옵션

에이전트는 상황에 따라 `health-sync` CLI(또는 직접 파이썬 스크립트)를 실행합니다:

```bash
# 기본 동기화 실행 (신규 활동 노트 생성 및 요약 출력)
health-sync run -p

# 에이전트 파이프라인 연동용 정형 JSON 단일 출력
health-sync run --json

# 동기화 완료 후 원본 소스 파일 자동 정리(휴지통 이동) 포함 실행
health-sync run -p --delete-source

# 특정 기간 데이터만 동기화
health-sync run --start-date YYYY-MM-DD --end-date YYYY-MM-DD -p

# 전체 재검사 (Full Rebuild)
health-sync run -f -p

# 동기화 현황 및 볼트 연결 상태 점검
health-sync status
```

> **CLI 미등록 환경 실행**:
> 전역 심링크가 없는 경우 스크립트 직접 호출:
> `cd tools/health-sync/src && uv run python main.py run --json`

---

## 2. 📋 JSON 출력 형식 및 결과 파싱

`--json` 옵션 사용 시 `stdout`에 다음 단일 JSON 객체가 출력됩니다:

```json
{
  "status": "success",
  "processed": 1,
  "skipped": 15,
  "deleted_source": 0,
  "duration_seconds": 4.82,
  "items": [
    {
      "key": "RUNNING-2026-09-14-0519",
      "type": "RUNNING",
      "date": "2026-09-14 05:19:24",
      "distance_km": 4.47,
      "duration": "26분 55초",
      "calories": 331
    }
  ]
}
```

---

## 3. 🧪 사후 검증 체크리스트

1. `status` 값이 `"success"`인지 확인.
2. `processed > 0`인 경우 사용자에게 새로 추가된 운동 종목, 날짜, 거리, 시간을 요약하여 보고.
3. 오류 발생 시 `health-sync status`를 실행하여 로컬 마운트 여부 및 Google Drive 접근 권한 확인.
