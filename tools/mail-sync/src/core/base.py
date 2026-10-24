from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import typer

@dataclass
class HandlerResult:
    handler_name: str
    success: bool
    processed_count: int = 0
    skipped_count: int = 0
    summary: str = ""
    items: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None

class BaseHandler(ABC):
    name: str = ""
    description: str = ""

    @abstractmethod
    def get_gmail_query(self, time_window_str: Optional[str] = None, month_str: Optional[str] = None) -> str:
        """핸들러 전용 1단계 Gmail 검색 쿼리 반환"""
        pass

    @abstractmethod
    def process(
        self,
        messages: List[Dict[str, Any]],
        config: Any,
        progress_callback: Optional[Callable[[str, Optional[float]], None]] = None,
    ) -> HandlerResult:
        """2단계: 필터링된 메일 목록을 파싱하고 저장소(Sheets/Obsidian)에 갱신"""
        pass

    def register_cli(self, sub_app: typer.Typer) -> None:
        """핸들러 전용 서브커맨드 등록 (선택적)"""
        pass
