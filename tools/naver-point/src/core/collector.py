"""Point harvesting and random card drawing engine."""

import asyncio
import logging
import random
import re
from typing import Callable, Optional
from core.config import NAVER_PAY_BENEFIT_URL, NAVER_CAMPAIGN_URL

logger = logging.getLogger(__name__)

BENEFIT_SELECTORS = [
    "button:has-text('포인트 받기')",
    "a:has-text('포인트 받기')",
    "button:has-text('뽑기')",
    "a:has-text('뽑기')",
    ".BenefitItem_btn__click",
]

BALANCE_SELECTORS = [
    ".my_point .num",
    ".point_num",
    "a[href*='point'] strong",
    "a[href*='point'] .num",
    "span:has-text('P')",
]


async def handle_extra_pages(context):
    """Close extra popup tabs created after clicking benefit buttons."""
    if not context:
        return
    pages = context.pages
    if len(pages) > 1:
        for p in pages[1:]:
            try:
                await p.wait_for_timeout(800)
                await p.close()
            except Exception:
                pass


async def fetch_point_balance(session) -> Optional[int]:
    """Extract current Naver Pay point balance from page."""
    page = session.page
    try:
        if "pay.naver.com" not in page.url:
            await page.goto(NAVER_PAY_BENEFIT_URL, wait_until="domcontentloaded", timeout=10000)
            await page.wait_for_timeout(1500)

        for selector in BALANCE_SELECTORS:
            el = await page.query_selector(selector)
            if el and await el.is_visible():
                text = (await el.text_content() or "").strip()
                # Find number with commas, e.g. "12,450"
                match = re.search(r"([\d,]+)", text)
                if match:
                    val_str = match.group(1).replace(",", "")
                    if val_str.isdigit():
                        return int(val_str)
    except Exception as e:
        logger.warning(f"Could not extract balance: {e}")
    return None


async def harvest_benefits(
    session,
    dry_run: bool = False,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> tuple[int, list[str]]:
    """Scan and click all available benefit point buttons."""
    page = session.page
    context = session.context

    logger.info("Navigating to Naver Pay benefit page...")
    await page.goto(NAVER_PAY_BENEFIT_URL, wait_until="domcontentloaded", timeout=15000)
    await page.wait_for_timeout(2000)

    if progress_callback:
        progress_callback("혜택 포인트 버튼 탐색 중...")

    all_buttons = []
    for sel in BENEFIT_SELECTORS:
        try:
            buttons = await page.query_selector_all(sel)
            for b in buttons:
                if await b.is_visible() and await b.is_enabled():
                    all_buttons.append(b)
        except Exception as e:
            logger.debug(f"Selector query error for {sel}: {e}")

    total = len(all_buttons)
    if dry_run:
        if progress_callback:
            progress_callback(f"[Dry-run] 수집 가능한 혜택 버튼 {total}개 감지됨")
        return total, [f"Button {i+1}" for i in range(total)]

    clicked_count = 0
    clicked_items = []

    for idx, btn in enumerate(all_buttons):
        if progress_callback:
            progress_callback(f"혜택 버튼 클릭 진행 중... ({idx + 1}/{total})")

        try:
            if await btn.is_visible() and await btn.is_enabled():
                btn_text = (await btn.text_content() or "").strip().replace("\n", " ")
                await btn.scroll_into_view_if_needed()
                await asyncio.sleep(random.uniform(1.0, 2.3))

                await btn.click(timeout=3000)
                clicked_count += 1
                clicked_items.append(btn_text or f"Button {idx+1}")
                logger.info(f"Clicked benefit button: {btn_text}")

                await handle_extra_pages(context)
        except Exception as e:
            logger.warning(f"Failed clicking benefit button {idx}: {e}")

    return clicked_count, clicked_items


async def harvest_random_draws(
    session,
    dry_run: bool = False,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> int:
    """Scan and click random point cards on the campaign page."""
    page = session.page

    logger.info("Navigating to Naver Pay random draw campaign...")
    await page.goto(NAVER_CAMPAIGN_URL, wait_until="domcontentloaded", timeout=15000)
    await page.wait_for_timeout(2000)

    draw_count = 0

    while True:
        target_locator = page.locator(".section_point_draw .draw_list a.card_draw").filter(
            has_text=re.compile(r"지금뽑기|한번 더")
        ).filter(visible=True)

        count = await target_locator.count()
        if count == 0:
            break

        if dry_run:
            if progress_callback:
                progress_callback(f"[Dry-run] 뽑기 가능한 카드 {count}개 감지됨")
            return count

        if progress_callback:
            progress_callback(f"랜덤 카드 뽑기 진행 중... ({draw_count}회 완료, {count}장 남음)")

        target = target_locator.first
        try:
            await target.scroll_into_view_if_needed()
            await asyncio.sleep(random.uniform(1.2, 2.0))

            try:
                await target.click(force=True, timeout=2000)
            except Exception:
                box = await target.bounding_box()
                if box:
                    await page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                else:
                    await target.evaluate("el => el.click()")

            draw_count += 1
        except Exception as e:
            logger.warning(f"Error clicking draw card: {e}")
            break

        # Wait and close popup
        await asyncio.sleep(random.uniform(2.0, 3.0))

        try:
            close_btn = page.locator('button.btn_close, .close, :text("닫기")').filter(visible=True).first
            if await close_btn.count() > 0:
                await close_btn.click(force=True, timeout=1500)
            else:
                await page.mouse.click(10, 10)
        except Exception as e:
            logger.debug(f"Popup close fallback: {e}")

        # Reload to synchronize card states
        try:
            await asyncio.sleep(random.uniform(1.0, 1.8))
            await page.reload(wait_until="domcontentloaded")
            await page.wait_for_timeout(1500)
        except Exception as e:
            logger.warning(f"Reload error during draw loop: {e}")
            break

    return draw_count
