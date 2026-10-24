import os
import glob
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

@dataclass
class MailSyncConfig:
    birth_date_6digit: str
    google_account: str
    gog_family_folder_id: str
    spreadsheet_name: str
    obsidian_vault_path: Optional[str]
    family_finance_dir: str
    is_local_vault: bool
    data_dir: str

def find_default_obsidian_family_path() -> tuple[Optional[str], Optional[str]]:
    """macOS Google Drive CloudStorage 내 옵시디언 vault 및 areas/family/finance 경로 자동 탐색"""
    home = os.path.expanduser("~")
    patterns = [
        os.path.join(home, "Library", "CloudStorage", "GoogleDrive-*", "내 드라이브", "obsidian"),
        os.path.join(home, "Library", "CloudStorage", "GoogleDrive-*", "My Drive", "obsidian"),
    ]
    
    for pat in patterns:
        matches = glob.glob(pat)
        for vault_cand in matches:
            family_cand = os.path.join(vault_cand, "areas", "family")
            if os.path.exists(family_cand):
                finance_cand = os.path.join(family_cand, "finance")
                return vault_cand, finance_cand

    return None, None

def load_config() -> MailSyncConfig:
    """환경변수 및 로컬 디렉토리 경로 로드"""
    base_src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(base_src_dir, ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)

    data_dir = os.path.join(base_src_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    birth_date = os.environ.get("BIRTH_DATE_6DIGIT", "")
    google_account = os.environ.get("GOOGLE_ACCOUNT", "minokim82@gmail.com")
    gog_folder_id = os.environ.get("GOG_FAMILY_FOLDER_ID", "1PaB7zVl7WsQCmODRxBRpImxFMa0fkV1q")
    spreadsheet_name = os.environ.get("SPREADSHEET_NAME", "가족_금융_원장")

    env_vault = os.environ.get("OBSIDIAN_VAULT_PATH")
    auto_vault, auto_finance = find_default_obsidian_family_path()

    vault_path = env_vault or auto_vault
    if vault_path:
        finance_dir = os.path.join(vault_path, "areas", "family", "finance")
    else:
        finance_dir = auto_finance or os.path.join(data_dir, "fallback_finance")

    is_local = bool(vault_path and os.path.exists(os.path.dirname(finance_dir)))

    # finance 디렉토리 및 statements 하위 폴더 생성 보장
    if is_local:
        os.makedirs(finance_dir, exist_ok=True)
        os.makedirs(os.path.join(finance_dir, "statements"), exist_ok=True)

    return MailSyncConfig(
        birth_date_6digit=birth_date,
        google_account=google_account,
        gog_family_folder_id=gog_folder_id,
        spreadsheet_name=spreadsheet_name,
        obsidian_vault_path=vault_path,
        family_finance_dir=finance_dir,
        is_local_vault=is_local,
        data_dir=data_dir,
    )
