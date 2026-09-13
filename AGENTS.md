# AGENTS.md

이 문서는 `my-tools` 저장소에서 작업하는 AI 에이전트들을 위한 개발 가이드라인, 아키텍처 원칙, 프로젝트 명세 및 코딩 컨벤션 지침서입니다.

---

## 1. 프로젝트 개요 (Overview)

`my-tools`는 개인이 직접 제작하여 사용하는 다양한 목적의 유틸리티, 자동화 스크립트, CLI 도구, MCP(Model Context Protocol) 서버 등을 지속적으로 개발하고 보관하는 **도구 모음 툴킷 모노레포(Toolkit Monorepo)**입니다.

### 1.1 핵심 목표
- **지속적 확장성**: 필요할 때마다 새로운 도구를 빠르고 안전하게 추가할 수 있는 유연한 구조.
- **도구 간 간섭 제로**: 서로 다른 기술 스택과 라이브러리 버전을 가진 도구들이 한 저장소에서 평화롭게 공존.
- **즉시 실행 가능성**: 작성된 도구는 언제든 로컬 환경(macOS)이나 터미널 전역(`~/.local/bin`), 또는 AI 에이전트(MCP)에서 즉각 실행 가능해야 함.

---

## 2. 프로젝트 철학 및 설계 원칙 (Core Principles)

1. **완전 독립 자립 원칙 (Zero-Coupling Policy)**
   - 모든 도구는 `./tools/<tool-name>/` 디렉토리 아래에 위치하며, 다른 도구나 상위 루트의 소스 코드를 직접 참조하지 않습니다.
   - 특정 도구 폴더 하나만 다른 머신이나 디렉토리로 복사해도 그 자체로 빌드되고 실행될 수 있는 **완전 자립형(Stand-alone)** 구조를 유지합니다.
   - 도구 간 코드 중복이 발생하더라도 초기에는 무리한 공통 패키지(`packages/shared` 등) 추출을 지양하고, 독립성을 우선시합니다.

2. **미니멀 스캐폴딩 필수 규격 (Minimal Scaffolding Standard)**
   - 어떤 언어나 형태로 작성되든 모든 도구는 `README.md`를 루트에 두고, 기능별로 `skill/`과 `src/` 서브폴더로 분리합니다:
     1. `README.md`: 도구의 목적, 필수 요구조건, 설치 방법, CLI 및 스킬 실행 예시 문서화 (인간 개발자 대상).
     2. `skill/SKILL.md`: AI 에이전트가 해당 도구를 자율적으로 이해하고 트리거할 수 있도록 제공하는 에이전트 스킬 명세서. 반드시 `/skill-creator` 스킬 표준(트리거 최적화 YAML frontmatter, 점진적 공개, 실행 절차)에 따라 생성.
     3. `src/` 의존성 명세: 언어별 표준 패키지 명세서(`pyproject.toml`, `package.json` 등).
     4. `src/` 명확한 진입점: 실행 가능한 진입점 파일(`main.py`, `index.ts`, `<tool-name>.sh` 등).
     5. `src/` 검증 수단: 정상 동작을 확인할 수 있는 최소 단위 테스트 또는 검증 스크립트.

3. **표준 툴체인 준수 (Standardized Polyglot Toolchains)**
   - 여러 언어의 사용을 허용하되, 언어별 패키지 관리 및 런타임 툴체인은 정해진 공식 표준을 준수합니다.
     - **Python**: `uv` 표준 (가상환경 격리 및 초고속 패키지 관리)
     - **TypeScript/Node**: `pnpm` (또는 `bun`)
     - **Shell(Zsh/Bash)**: POSIX/Zsh 표준 준수, 실행 권한(`chmod +x`) 명시
     - **Go/Rust**: `go.mod` / `Cargo.toml` 표준 준수

4. **철저한 비밀값 격리 (Isolated Secrets & Config)**
   - 각 도구에 필요한 API 키나 환경변수는 도구의 `src/.env` 파일로만 관리합니다.
   - `.env` 파일은 절대 Git에 커밋되지 않도록 `.gitignore`에 등록되어야 하며, 에이전트는 신규 도구 생성 시 반드시 더미 키가 포함된 `src/.env.example`을 함께 생성해야 합니다.

5. **루트 카탈로그 동기화 의무 (Catalog Synchronization)**
   - 새 도구를 생성하거나 기존 도구를 삭제/개편한 경우, 반드시 루트 [README.md](README.md)의 **도구 카탈로그(Tools Catalog) 표**를 즉시 최신화해야 합니다.

---

## 3. 디렉토리 구조 (Directory Structure)

```text
my-tools/
├── docs/                         # 프로젝트 문서 및 아키텍처 결정 기록
│   └── decisions.md              # 운영 지침 및 결정 기록 (ADR SSOT)
├── tools/                        # 모든 개별 도구들의 독립 서브 디렉토리
│   └── <tool-name>/              # 개별 도구 표준 컨테이너 (Stand-alone)
│       ├── README.md             # 도구 종합 가이드 (인간 개발자용)
│       ├── skill/                # 에이전트 스킬 전용 디렉토리 (노이즈 격리)
│       │   └── SKILL.md          # 에이전트 스킬 명세서 (/skill-creator로 생성)
│       └── src/                  # 도구 구현체 및 테스트
│           ├── pyproject.toml    # 언어별 의존성 정의 (또는 package.json 등)
│           ├── .env.example      # 환경변수 템플릿
│           ├── main.py           # 실행 진입점 (또는 <tool-name>.sh, index.ts 등)
│           └── tests/            # 단위 테스트
├── Makefile                      # 도구 목록, 전역 CLI 심링크, 에이전트 스킬 심링크 오케스트레이션
├── AGENTS.md                     # AI 에이전트 개발 가이드라인 및 프로젝트 SSOT
├── README.md                     # 프로젝트 소개 및 도구 전체 카탈로그
└── .gitignore                    # 글로벌 및 도구별 배제 패턴 (.env, .venv, node_modules 등)
```

---

## 4. 도구 생성 및 관리 워크플로우 (New Tool Workflow & Standards)

AI 에이전트가 새로운 도구를 추가할 때는 반드시 다음 단계를 순서대로 수행합니다.

### 4.1 신규 도구 생성 절차 (Step-by-Step)
1. **디렉토리 생성**:
   - `tools/<tool-name>/` 폴더 생성.
   - 하위에 `tools/<tool-name>/skill/` 및 `tools/<tool-name>/src/` 생성.
2. **언어별 표준 환경 구성 (in `src/`)**:
   - Python: `cd tools/<tool-name>/src && uv init --bare` 또는 `pyproject.toml` 작성 후 `uv venv`
   - TypeScript: `cd tools/<tool-name>/src && pnpm init`
   - Shell: `tools/<tool-name>/src/<tool-name>.sh` 스크립트 파일 작성 후 `chmod +x`
3. **핵심 로직 및 진입점 구현**: `src/` 내에 YAGNI 원칙에 따라 과도한 추상화 없이 직관적인 코드로 작성.
4. **인간 개발자용 README.md 작성 (`tools/<tool-name>/README.md`)**:
   - 도구명 및 한 줄 설명
   - 도구 분류 태그: `[CLI]`, `[MCP]`, `[SCRIPT]`, `[WEB]` 등
   - 설치 및 의존성 세팅 명령 (Copy-paste 가능하도록 작성)
   - CLI 실행 방법 및 에이전트 스킬 연동법 안내
5. **에이전트용 SKILL.md 작성 (`tools/<tool-name>/skill/SKILL.md`)**:
   - AI 에이전트가 해당 도구를 자율적으로 인지하고 필요할 때 즉시 트리거하여 사용할 수 있도록 `skill/` 폴더에 `SKILL.md` 생성.
   - 반드시 `/skill-creator` 스킬의 지침을 따라 작성:
     - YAML frontmatter: `name`과 `description`에 구체적인 트리거 맥락(언제 사용할지 구체적인 키워드 및 상황)을 적극적으로 명시 (언더트리거링 방지).
     - 본문: 3단계 점진적 공개(Metadata -> Body -> Resources), 실행 명령어 및 옵션, 입출력 포맷, 실패 시 해결책.
6. **검증 및 테스트**: `src/tests/` 단위 테스트 실행 또는 실제 샘플 입력을 통한 동작 검증.
7. **루트 카탈로그 업데이트**: 루트 [README.md](README.md)의 Tools Catalog 표에 새 도구 추가.

### 4.2 전역 실행 등록 가이드라인 (CLI Symlink & Skill Symlink)
- **CLI 도구 전역 등록**:
  - 루트 Makefile을 통해 간편하게 심링크를 등록/해제:
    ```bash
    make link tool=<tool-name>      # ~/.local/bin/<tool-name> 에 심링크
    make unlink tool=<tool-name>    # 심링크 해제
    ```
- **에이전트 스킬 전역 등록**:
  - `skill/` 디렉토리를 에이전트 전역 스킬 디렉토리에 원클릭 심링크:
    ```bash
    make link-skill tool=<tool-name>    # ~/.gemini/config/skills/<tool-name> 에 심링크
    make unlink-skill tool=<tool-name>  # 스킬 심링크 해제
    ```

---

## 5. 기술 스택 및 개발 규칙 (Tech Stack & Conventions)

### 5.1 표준 툴체인 명세
- **Python**: Python 3.11+, 패키지 매니저는 반드시 `uv` 사용 (`uv run`, `uv add`).
- **Node / TypeScript**: Node 20+ LTS, 패키지 매니저는 `pnpm` (또는 `bun`) 사용.
- **Shell**: macOS 기본 `zsh` 또는 POSIX 호환 `bash`.
- **Formatting/Linting**:
  - Python: `ruff`
  - TS/JS: `prettier` / `biome`
  - Shell: `shellcheck`

### 5.2 Git 커밋 원칙 및 타이밍 (Conventional Commits & Commit Timing)
모든 커밋은 변경된 도구의 이름을 스코프로 명시하며, 명확한 완료 시점에 원자적(Atomic)으로 커밋합니다.

1. **커밋 메시지 형식**: `<type>(<scope>): <description>`
   - `feat(<tool-name>)`: 신규 도구 추가 또는 도구 기능 추가
   - `fix(<tool-name>)`: 특정 도구의 버그 수정
   - `docs`: 문서 작성 및 갱신 (`AGENTS.md`, [README.md](README.md))
   - `docs(<tool-name>)`: 특정 도구의 문서 수정
   - `refactor(<tool-name>)`: 동작 변경 없는 리팩토링
   - `chore`: 루트 레벨 Makefile, 설정 파일, 공통 빌드 설정 변경

2. **언제 커밋하는가? (Commit Timing & Granularity)**:
   - **논리적 작업 단위(마일스톤) 완료 즉시**:
     - **신규 도구 완성 시**: 코드(`src/`) + 스킬(`skill/SKILL.md`) + 설명서(`README.md`) + 테스트 통과 + 루트 [README.md](README.md) 카탈로그 등록까지 한 사이클이 완전히 끝났을 때 1개 커밋으로 묶어 커밋.
     - **기능 추가 및 버그 수정 완료 시**: 특정 도구의 기능 구현 및 테스트 통과가 검증된 즉시 커밋.
     - **공통 규칙 및 문서 갱신 시**: `AGENTS.md`, `docs/decisions.md`, 루트 설정 변경 완료 즉시 커밋.
   - **사용자 승인(컨펌) 직후**: 사용자와 특정 설계나 구현에 대해 합의를 마쳤을 때 작업 유실 방지를 위해 즉각 커밋.

3. **커밋 전 필수 체크리스트 (Pre-Commit Checklist)**:
   - [ ] **테스트 및 동작 검증 완료**: 깨진 코드나 실행 오류가 있는 상태로는 절대 커밋하지 않음 (Never commit broken code).
   - [ ] **비밀값 격리 확인**: `git status`로 `.env` 파일이나 민감한 API 키가 스테이징에 포함되지 않았는지 점검.
   - [ ] **루트 카탈로그 동기화**: 새 도구 추가/삭제 시 루트 [README.md](README.md)가 함께 반영되었는지 확인.
   - [ ] **순수 상대 경로 준수**: 저장소 파일 내에 로컬 머신 절대 경로(`file:///...`)가 커밋되지 않도록 확인.

### 5.3 문서화 및 경로 원칙 (Portable Relative Links)
- 저장소 내의 모든 Markdown 파일(`.md`) 및 코드 주석 내 링크는 반드시 Git 기준 **순수 상대 경로**(`README.md`, `docs/decisions.md` 등)를 사용합니다.
- 로컬 머신 절대 경로(`file:///Users/...`)를 저장소 파일에 커밋하는 것은 엄격히 금지됩니다 (다른 머신에서 `git clone` 시 링크 깨짐 방지).

---

## 6. 지속 학습 및 문서 자가 갱신 지침 (Continuous Evolution & Living Document)

프로젝트 개발 과정에서 새로운 정책, 아키텍처 결정사항, 유용한 노하우나 트러블슈팅 경험이 도출될 경우 `AGENTS.md`를 능동적으로 최신화합니다.

### 6.1 자가 갱신 절차 (Update Flow)
1. **능동적 감지 및 제안**:
   - 사용자와의 대화 중 새로운 아키텍처 원칙, 도구 작성 규칙, 워크플로우 결정사항이 확인되면 에이전트가 *"이 내용을 AGENTS.md에 반영할까요?"*라고 제안하고 사용자 동의 후 반영합니다.
   - 사용자가 명시적으로 기록을 요청한 경우 즉시 반영합니다.
2. **기록 영역 구분**:
   - 구조/스택/표준 규칙의 변경: 해당 섹션(2~5번) 본문을 직접 수정하여 문서의 일관성을 유지합니다.
   - 중요한 아키텍처 결정 및 운영 정책: [docs/decisions.md](docs/decisions.md)에 ADR 형식으로 누적 기록합니다.
3. **README.md 동기화 의무**:
   - 신규 도구 추가, 환경변수 추가, 실행 스크립트 변경 등 사용자 온보딩 및 도구 목록에 영향을 미치는 변경이 있을 경우 반드시 [README.md](README.md)도 함께 동기화 갱신합니다.

---

## 7. 운영 지침 및 결정 기록 (Operational Learnings & Decisions)

프로젝트 개발 및 운영 과정에서 결정된 아키텍처 의사결정 기록(ADR)과 트러블슈팅 노하우는 [docs/decisions.md](docs/decisions.md)에서 전문을 관리합니다.

새로운 결정 사항이나 정책이 발생할 때마다 해당 문서에 ADR-12, ADR-13 순으로 누적 기록하십시오.

- **상세 기록 확인**: [docs/decisions.md](docs/decisions.md)
  - `ADR-1`: `./tools/<tool-name>` 전용 컨테이너 폴더 구조 채택
  - `ADR-2`: 완전 독립 자립 원칙 (Zero-Coupling Policy) 확정
  - `ADR-3`: 표준 툴체인 선정 (Python `uv`, TS `pnpm`)
  - `ADR-4`: 도구별 격리된 `src/.env` 및 `src/.env.example` 필수화
  - `ADR-5`: 루트 카탈로그 및 문서 자가 갱신(Living Document) 지침 도입
  - `ADR-6`: 스코프 기반 Conventional Commits 채택
  - `ADR-7`: 에이전트 연동용 SKILL.md 필수 동봉 및 /skill-creator 표준화
  - `ADR-8`: 도구 내부의 skill/ 및 src/ 이원화 서브폴더 구조 채택
  - `ADR-9`: 운영 지침 및 결정 기록의 docs/ 분리 및 모듈화
  - `ADR-10`: 저장소 내 문서 참조 시 순수 상대 경로 강제 (Portable Relative Links)
  - `ADR-11`: 커밋 타이밍 및 사전 체크리스트(Pre-Commit Checklist) 수립
