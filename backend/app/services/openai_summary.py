from openai import OpenAI

from ..config import settings


class OpenAISummaryService:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.openai_api_key)

    def summarize_article(self, *, title: str, press_name: str, raw_content: str) -> str:
        response = self.client.responses.create(
            model=settings.openai_model,
            reasoning={"effort": settings.openai_reasoning_effort},
            instructions=(
                "You are a news summarization assistant. "
                "Summarize the article in Korean in 3-4 concise sentences. "
                "Keep factual accuracy, avoid speculation, and do not mention that you are an AI."
            ),
            input=[
                {
                    "role": "developer",
                    "content": (
                        "Return only the final Korean summary text. "
                        "Do not use bullets, markdown, or headings."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"언론사: {press_name}\n"
                        f"제목: {title}\n"
                        f"본문:\n{raw_content}"
                    ),
                },
            ],
        )
        return response.output_text.strip()
