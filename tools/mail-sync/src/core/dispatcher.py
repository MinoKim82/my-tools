import importlib
import logging
import os
import pkgutil
from typing import Callable, Dict, List, Optional
from core.base import BaseHandler, HandlerResult
from core.config import MailSyncConfig
from core.gog_client import GogClient
from core.state import StateManager

logger = logging.getLogger(__name__)

class Dispatcher:
    def __init__(self, config: MailSyncConfig, gog_client: GogClient, state_manager: StateManager):
        self.config = config
        self.gog = gog_client
        self.state = state_manager
        self.handlers: Dict[str, BaseHandler] = {}
        self.discover_handlers()

    def register_handler(self, handler: BaseHandler) -> None:
        self.handlers[handler.name] = handler

    def discover_handlers(self) -> None:
        """handlers/ 디렉토리 내 모든 BaseHandler 구현체 자동 탐색 및 등록"""
        handlers_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "handlers")
        if not os.path.exists(handlers_dir):
            return

        for _, module_name, is_pkg in pkgutil.iter_modules([handlers_dir]):
            if not is_pkg and not module_name.startswith("__"):
                try:
                    mod = importlib.import_module(f"handlers.{module_name}")
                    for attr_name in dir(mod):
                        cls = getattr(mod, attr_name)
                        if isinstance(cls, type) and issubclass(cls, BaseHandler) and cls is not BaseHandler:
                            instance = cls()
                            if instance.name:
                                self.register_handler(instance)
                except Exception as e:
                    logger.error(f"Failed to load handler '{module_name}': {e}")

    def build_time_window_str(self, days: int = 1, month: Optional[str] = None, all_time: bool = False) -> Optional[str]:
        """쿼리 시간 범위 제약조건 문자열 생성"""
        if all_time:
            return None
        if month:
            # month format: YYYY-MM
            try:
                parts = month.split("-")
                y = int(parts[0])
                m = int(parts[1])
                start_date = f"{y}/{m:02d}/01"
                if m == 12:
                    end_date = f"{y+1}/01/01"
                else:
                    end_date = f"{y}/{m+1:02d}/01"
                return f"after:{start_date} before:{end_date}"
            except Exception:
                pass
        # default to newer_than:Nd
        return f"newer_than:{days}d"

    def run(
        self,
        target_handlers: Optional[List[str]] = None,
        days: int = 1,
        month: Optional[str] = None,
        all_time: bool = False,
        progress_callback: Optional[Callable[[str, Optional[float]], None]] = None,
    ) -> List[HandlerResult]:
        """등록된 핸들러 실행 및 2단 파이프라인 수행"""
        results: List[HandlerResult] = []
        handlers_to_run = [
            h for name, h in self.handlers.items()
            if not target_handlers or name in target_handlers
        ]

        if not handlers_to_run:
            logger.warning("No matching handlers to run.")
            return results

        time_window = self.build_time_window_str(days=days, month=month, all_time=all_time)

        for handler in handlers_to_run:
            msg_prefix = f"[{handler.name}]"
            if progress_callback:
                progress_callback(f"{msg_prefix} Gmail 검색 조건 생성 및 조회 중...", None)

            query = handler.get_gmail_query(time_window_str=time_window, month_str=month)
            raw_messages = self.gog.search_messages(query, max_results=50)

            # 중복 체크 (이미 처리된 message ID 필터링)
            unprocessed_messages = []
            skipped_count = 0
            for m in raw_messages:
                m_id = m.get("id") or m.get("threadId")
                if m_id and not self.state.is_processed(m_id):
                    unprocessed_messages.append(m)
                else:
                    skipped_count += 1

            if progress_callback:
                progress_callback(
                    f"{msg_prefix} 검색 완료: 신규 {len(unprocessed_messages)}건 (기처리 {skipped_count}건 제외)",
                    None
                )

            if not unprocessed_messages:
                res = HandlerResult(
                    handler_name=handler.name,
                    success=True,
                    processed_count=0,
                    skipped_count=skipped_count,
                    summary=f"신규 처리 대상 없음 (기처리 {skipped_count}건)",
                )
                results.append(res)
                continue

            # 2단계: 핸들러 실행
            try:
                res = handler.process(
                    unprocessed_messages,
                    self.config,
                    progress_callback=progress_callback
                )
                res.skipped_count = skipped_count
                
                # 성공 처리된 메시지 상태 저장
                for item in res.items:
                    msg_id = item.get("message_id")
                    if msg_id:
                        self.state.mark_processed(msg_id, handler.name, meta=item)

                results.append(res)
            except Exception as e:
                logger.error(f"Error executing handler {handler.name}: {e}", exc_info=True)
                results.append(HandlerResult(
                    handler_name=handler.name,
                    success=False,
                    processed_count=0,
                    skipped_count=skipped_count,
                    summary=f"실행 중 예외 발생: {str(e)}",
                    error_message=str(e),
                ))

        return results
