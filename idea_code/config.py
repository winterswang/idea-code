"""配置常量。不再包含 ProviderConfig —— 由 AgentContext 统一管理。"""

import os
from dotenv import load_dotenv

load_dotenv(override=True)

WORKDIR = os.getcwd()
MAX_ROUNDS = int(os.getenv("IDEA_MAX_ROUNDS", "10"))
PROJECTS_DIR = os.path.join(WORKDIR, "projects")
VERBOSE_LOG = os.getenv("IDEA_VERBOSE_LOG", "").strip() == "1"
API_TIMEOUT_SECS = int(os.getenv("IDEA_API_TIMEOUT", "300"))
REQUIRED_ENV_VARS = [
    "IDEA_API_KEY",
    "REV_A_API_KEY",
    "REV_B_API_KEY",
]

def validate_env() -> list[str]:
    """检查必填环境变量，返回缺失列表。"""
    missing = [k for k in REQUIRED_ENV_VARS if k not in os.environ or not os.environ[k]]
    return missing

