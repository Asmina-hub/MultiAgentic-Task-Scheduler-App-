from langchain.chat_models import init_chat_model
from slot_planner.config import settings

def llm_init(provider :str|None= None, temperature:float=0, fallback: bool =True):
    provider = provider or settings.default_provider

    if provider == "anthropic":
        return init_chat_model(
            settings.anthropic_model,
            model_provider="anthropic",
            api_key=settings.anthropic_api_key,
            temperature=temperature,
        )

    if provider == "tud":
        return init_chat_model(
            settings.tud_model,
            model_provider="openai",
            base_url=settings.tud_base_url,
            api_key=settings.tud_api_key,
            temperature=temperature,
            extra_body={"disable_fallbacks": not fallback},
        )
    raise ValueError(f"unknown provider: {provider}")


