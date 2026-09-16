# health-sync [CLI] [OBSIDIAN] [HEALTH]

Android의 **Health Sync** 앱을 통해 수집된 피트니스 활동 데이터(CSV, FIT, GPX)를 **Obsidian 보관함(Vault)**의 운동 일지 마크다운 노트와 GPX 지도 경로 파일로 자동 동기화하는 CLI 도구입니다.

---

## 🚀 주요 특징

1. **하이브리드 스토리지 공급자 (Hybrid Provider)**:
   - macOS Google Drive 데스크톱 로컬 마운트(`~/Library/CloudStorage/...`)를 자동 감지하여 네트워크 지연 없이 초고속 로컬 파일 I/O로 동기화합니다.
   - 마운트 미발견 시 시스템의 `gog` CLI를 통해 원격 구글 드라이브 스캔, 다운로드, 업로드로 자동 폴백합니다.
2. **FIT 바이너리 정밀 분석**:
   - Garmin/Samsung 바이너리 FIT 파일에서 심박수, 칼로리, 페이스, 케이던스, 수영 스트로크/SWOLF 지표 및 1km 구간별 Lap 기록을 파싱합니다.
3. **Obsidian Leaflet 연동**:
   - 동명 GPX 파일을 Obsidian 볼트 하위 폴더로 복사하고 마크다운 본문에 ````leaflet```` 블록을 자동 생성합니다.
4. **듀얼 출력 인터페이스**:
   - 인간 사용자를 위한 `rich` 콘솔 진행률 및 테이블 요약.
   - AI 에이전트 및 cron 스크립트를 위한 단일 라인 `--json` 출력.

---

## ⚙️ 설치 및 설정

### 1. 의존성 설치
```bash
cd tools/health-sync/src
uv sync
```

### 2. 환경 변수 설정 (선택 사항)
로컬 Google Drive 마운트 경로를 자동으로 탐색하므로 기본 상태에서는 설정 없이 즉시 구동됩니다. 사용자 정의 경로가 필요한 경우 `tools/health-sync/src/.env` 파일을 생성합니다.

```env
# Google Drive 원격 폴더 ID (gog CLI 폴백용)
GOG_SOURCE_FOLDER_ID="1cLQ-wLPwGXky2KrvMctZUvUfzUGAnH-f"
GOG_TARGET_FOLDER_ID="11r4bcpUZ2IFEqDS7jl3JT1ZiC4e1oqNH"
```

---

## 🏃 CLI 사용법

### 전역 실행 심링크 등록 (Makefile)
```bash
make link tool=health-sync
```

### 실행 명령어

```bash
# 1. 기본 동기화 실행 (신규 활동 자동 감지 및 노트 생성)
health-sync run

# 2. 신규 생성 활동 한 줄 요약 출력
health-sync run -p

# 3. 특정 날짜 범위 동기화
health-sync run --start-date 2026-09-01 --end-date 2026-09-15 -p

# 4. 동기화 성공 후 소스 파일 정리 (휴지통 이동)
health-sync run --delete-source

# 5. 캐시 무시 전체 재스캔 (Full Rebuild)
health-sync run -f

# 6. 기계 판독용 JSON 출력 (에이전트/스크립트 연동)
health-sync run --json

# 7. 현재 동기화 상태 및 연결 정보 확인
health-sync status
```

---

## 🤖 에이전트 스킬 연동

에이전트 전역 스킬 디렉토리에 심링크 등록:
```bash
make link-skill tool=health-sync
```
등록 후 AI 에이전트에게 *"운동 데이터 동기화해줘"*, *"헬스 데이터 옵시디언에 넣어줘"* 등의 명령으로 즉시 호출할 수 있습니다.
