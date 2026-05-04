from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

load_dotenv()

DEEPSEEK_V4_FLASH = ChatAnthropic(
    model_name="deepseek-v4-flash",
    timeout=20,
    max_retries=2,
    stop=None,
)
