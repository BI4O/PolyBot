from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

DEEPSEEK_V4_FLASH = ChatOpenAI(
    model="deepseek-v4-flash",
    timeout=20,
    max_retries=2,
)
