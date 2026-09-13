# my-tools

개인 유틸리티, CLI 도구, 자동화 스크립트, MCP(Model Context Protocol) 서버 등을 직접 제작하고 보관하는 **도구 모음 툴킷 모노레포**입니다.

모든 도구는 `./tools/<tool-name>/` 하위에 위치하며, 각자 독립된 가상환경과 의존성을 가지는 **완전 자립형(Zero-Coupling)** 구조로 관리됩니다.

---

## 🛠 Tools Catalog

현재 등록된 도구 목록입니다. 신규 도구가 추가될 때마다 지속적으로 업데이트됩니다.

| 도구명 | 유형 (Tag) | 기술 스택 | 설명 | 경로 |
|---|---|---|---|---|
| *(첫 번째 도구 준비 중)* | - | - | 도구 추가 시 여기에 등록됩니다. | `tools/` |

> 💡 **도구 유형 태그**: `[CLI]`, `[MCP]`, `[SCRIPT]`, `[WEB]`, `[BOT]`

---

## 🚀 Quick Start

### 1. 도구 목록 확인
```bash
make list
```

### 2. 특정 도구 전역 등록 (Dual Interface: CLI & Agent Skill)
- **CLI 전역 등록 (`~/.local/bin/`)**:
  ```bash
  make link tool=<tool-name>        # 등록
  make unlink tool=<tool-name>      # 해제
  ```
  > **참고**: `~/.local/bin`이 `PATH` 환경변수에 추가되어 있어야 합니다 (`export PATH="$HOME/.local/bin:$PATH"` in `~/.zshrc`).

- **에이전트 스킬 등록 (`~/.gemini/config/skills/`)**:
  ```bash
  make link-skill tool=<tool-name>    # 등록 (AI 에이전트가 즉시 도구를 스킬로 사용)
  make unlink-skill tool=<tool-name>  # 해제
  ```

---

## 📁 Repository Structure

```text
my-tools/
├── docs/                         # 프로젝트 문서 및 아키텍처 결정 기록
│   └── decisions.md              # 운영 지침 및 결정 기록 (ADR SSOT)
├── tools/                        # 모든 개별 도구들의 독립 서브 디렉토리
│   └── <tool-name>/              # 개별 도구 표준 컨테이너 (Stand-alone)
│       ├── README.md             # 도구 종합 가이드 (인간 개발자용)
│       ├── skill/                # 에이전트 스킬 전용 폴더 (노이즈 격리)
│       │   └── SKILL.md          # 에이전트 스킬 명세 (/skill-creator로 생성)
│       └── src/                  # 도구 구현체 및 테스트
│           ├── pyproject.toml    # 언어별 의존성 정의 (또는 package.json 등)
│           ├── .env.example      # 환경변수 템플릿
│           ├── main.py           # 실행 진입점 (또는 <tool-name>.sh, index.ts 등)
│           └── tests/            # 단위 테스트
├── Makefile                      # 도구 목록, CLI/스킬 심링크 오케스트레이션
├── AGENTS.md                     # AI 에이전트 개발 가이드라인 및 SSOT
├── README.md                     # 프로젝트 소개 및 도구 카탈로그
└── .gitignore                    # 글로벌 배제 패턴 (.env, .venv 등)
```

---

## 🤖 AI Agent Guidelines

이 저장소에서 AI 코딩 에이전트(Antigravity, Claude Code 등)와 함께 작업할 때는 [AGENTS.md](AGENTS.md)의 지침을 엄격히 준수합니다.

- **Zero-Coupling**: 도구 간 소스코드 직접 참조 금지 (완전 자립형).
- **최소 스캐폴딩 5대 규격**: `README.md`(개발자용), `SKILL.md`(`/skill-creator` 기반 에이전트용), 진입점, 의존성 명세, 테스트.
- **에이전트 스킬 연동**: 새 도구 생성 시 반드시 `/skill-creator` 지침에 따라 트리거 최적화된 `SKILL.md`를 동봉하여 AI 에이전트가 즉각 호출할 수 있도록 구성.
- **동기화 의무**: 새 도구 추가 시 본 [README.md](README.md)의 **Tools Catalog** 갱신 필수.
- **자가 갱신(Living Document)**: 새로운 아키텍처 결정이나 노하우는 [docs/decisions.md](docs/decisions.md)에 ADR 형식으로 누적 기록.
- **이식성 높은 상대 경로**: 저장소 내 모든 Markdown 링크는 반드시 상대 경로를 사용하여 다른 환경에서 `git clone` 시에도 링크가 유지되도록 관리.
