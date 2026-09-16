# health-sync AI Agent 개발 및 유지보수 가이드 (SSOT)

이 문서는 `tools/health-sync` 도구를 개발, 유지보수, 확장하는 AI 에이전트를 위한 서브프로젝트 전용 아키텍처 명세서이자 개발 지침서입니다.  
프로젝트 전역 규칙은 루트 [AGENTS.md](../../AGENTS.md)를 참조하십시오.

---

## 1. 서브프로젝트 개요 및 설계 철학

`health-sync`는 Android Health Sync 앱이 Google Drive로 내보낸 건강/피트니스 활동 데이터(CSV, FIT, GPX)를 수집하여 **Obsidian 보관함(Vault)** 내에 체계적인 마크다운 분석 노트와 GPX 지도 경로 파일로 자동 동기화하는 도구입니다.

### 1.1 핵심 설계 목표
- **하이브리드 스토리지 공급자 (Hybrid Provider)**:
  - Google Drive 데스크톱 로컬 마운트(`~/Library/CloudStorage/...`)를 1순위로 탐색하여 네트워크 지연 없는 초고속 파일 I/O 수행.
  - 마운트 미발견 시 `gog` CLI 원격 API로 자동 폴백하여 무인/원격 환경에서도 정상 동작 보장.
- **비파괴적 안전 기본값 (Safe Retention)**:
  - 기본 실행 시 원본 소스 파일(`Health Sync 활동`)을 보존하며, `--delete-source` 플래그 명시 시에만 성공적으로 노트/GPX가 생성된 파일을 안전하게 정리.
- **듀얼 출력 인터페이스 (Human vs Machine)**:
  - 터미널 직접 실행: `rich` 콘솔의 프로그레스 바, 상세 로그, 운동 요약 테이블 출력.
  - 에이전트/자동화 스크립트 실행(`--json`): 표준 출력(`stdout`)에 단 한 줄의 정형 JSON 결과만 출력.

---

## 2. CLI 명령어 및 작업 워크플로 (Commands)

| 작업 | 명령어 | 설명 |
|---|---|---|
| 의존성 동기화 | `cd tools/health-sync/src && uv sync` | 가상환경 및 패키지 설치 |
| 기본 동기화 | `uv run python main.py run` | 미처리 활동 자동 스캔 및 Obsidian 노트 생성 |
| 한 줄 요약 출력 | `uv run python main.py run -p` | 신규 생성된 활동의 요약 한 줄 출력 |
| 원본 파일 정리 | `uv run python main.py run --delete-source` | 생성 완료된 원본 파일 자동 삭제/휴지통 이동 |
| 날짜 범위 지정 | `uv run python main.py run --start-date 2026-08-01 --end-date 2026-08-31` | 특정 기간 활동만 필터링 |
| 전체 강제 재스캔 | `uv run python main.py run -f` | 캐시 무시 전체 재검사 및 동기화 상태 재구성 |
| 기계 판독 JSON | `uv run python main.py run --json` | 에이전트 파이프라인용 단일 라인 JSON 출력 |
| 상태 확인 | `uv run python main.py status` | 마지막 동기화 시간 및 누적 처리 통계 출력 |
| 테스트 실행 | `cd tools/health-sync/src && uv run pytest` | 파서, 빌더, 공급자 단위/통합 테스트 |
| 린트 및 포맷 | `uv run ruff check . && uv run ruff format .` | 코드 컨벤션 검증 |

---

## 3. 아키텍처 및 모듈 구성 (`src/`)

```text
tools/health-sync/
├── README.md               # 사용자 및 개발자 가이드
├── AGENTS.md               # 에이전트 전용 개발/유지보수 지침서 (본 문서)
├── skill/
│   └── SKILL.md            # 에이전트 런타임 스킬 명세서
└── src/
    ├── health-sync.sh      # 전역 심링크 CLI 래퍼 (uv run)
    ├── pyproject.toml      # uv 패키지 명세서 (typer, rich, fitparse, pyyaml)
    ├── .env.example        # 환경변수 템플릿
    ├── main.py             # Typer 기반 CLI 진입점 (run, status)
    ├── core/
    │   ├── config.py       # 경로 자동 탐색 및 환경변수 로더
    │   ├── provider.py     # HybridStorageProvider (Local vs Gog CLI)
    │   ├── status.py       # SyncStatusManager (.sync_status.json)
    │   ├── parser/
    │   │   ├── csv_parser.py   # 메타데이터 추출 및 시간 파싱
    │   │   └── fit_parser.py   # 바이너리 FIT 세부 지표/Lap 파싱
    │   └── builder/
    │       └── obsidian_builder.py # 운동별 동적 마크다운 및 GPX 연동
    └── tests/              # 단위 및 통합 테스트
```

---

## 4. 핵심 데이터 규칙 및 Gotchas (Non-Obvious Patterns)

### 4.1 5분 허용오차 파일 결합 규칙 (Fuzzy Time Matching)
- CSV, FIT, GPX 파일은 생성 시점 초 단위가 조금씩 다를 수 있습니다.
- **기준점**: CSV 파일의 `날짜` 필드를 파싱하여 `YYYY-MM-DD-HHMM` 고유 키를 생성합니다.
- **매칭 조건**: CSV의 운동 시작 시간과 FIT/GPX 파일명에 포함된 시간의 차이가 **5분(300초) 이내**일 경우 동일 운동 세트로 바인딩합니다.

### 4.2 중복 생성 방지 2단계 검증
1. **메모리/캐시 검사**: `.sync_status.json`의 `processed_activities` 세트에서 키 존재 여부 확인.
2. **타깃 폴더 파일시스템 검사**: 타깃 디렉토리(`workout/{activity}/[KEY].md`)에 해당 마크다운이 이미 존재하는지 검사하여 불필요한 FIT 파싱을 사전에 차단.

### 4.3 FIT 바이너리 파싱 및 단위 환산 규칙
- **러닝 (RUNNING)**:
  - 심박수(bpm), 페이스(min/km), 케이던스(spm, 보폭 환산 주의).
  - Lap 메시지에서 구간별 1km 거리, 소요 시간, 평균 페이스 추출.
- **수영 (SWIMMING)**:
  - 총 스트로크 수, 평균 SWOLF(소요시간(초) + 스트로크 수), 풀 길이(25m/50m) 구간별 영법(자유형, 평영 등) 및 페이스(/100m) 환산.

### 4.4 Obsidian Leaflet GPX 연동 블록
- 마크다운 파일과 동일한 하위 폴더에 `[KEY].gpx`를 복사/배치하고, 노트 본문 하단에 다음 형식으로 삽입:
  ````markdown
  ```leaflet
  id: <소문자-key>
  gpx: [[<KEY>.gpx]]
  ```
  ````

---

## 5. 에이전트 준수 가이드라인 (Crucial Guardrails)

1. **비밀값 및 로컬 캐시 커밋 금지**: `.env`, `.sync_status.json`, `.cache/`는 절대 커밋하지 않습니다.
2. **순수 상대 경로 준수**: 본 문서와 코드 주석 내 링크는 Git 기준 상대 경로를 사용합니다.
3. **기계 판독용 JSON 출력 무결성 (`--json`)**:
   - `--json` 실행 시 `stdout`에는 오직 단일 라인의 JSON만 출력되어야 합니다:
     ```json
     {"status": "success", "processed": 2, "skipped": 15, "deleted_source": 0, "duration_seconds": 1.45}
     ```
   - 모든 프로그레스 바, 로그는 `stderr`로 출력해야 파이프라인 파싱 에러를 방지할 수 있습니다.
