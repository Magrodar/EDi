from app.config import settings
from app.llm.base import ExtractionProvider
from app.llm.stub import StubExtractionProvider


def get_extraction_provider() -> ExtractionProvider:
    if settings.edi_llm_provider == "openai":
        from app.llm.openai_provider import OpenAIExtractionProvider

        return OpenAIExtractionProvider()
    return StubExtractionProvider()
