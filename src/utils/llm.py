import os
from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel

load_dotenv()

def get_llm(temperature: float = 0.0) -> BaseChatModel:
    provider = os.getenv("LLM_PROVIDER", "huggingface").lower()
    
    if provider in ["huggingface", "hf"]:
        from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
        api_token = os.getenv("HUGGINGFACEHUB_API_TOKEN") or os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_API_KEY", "")
        model_name = os.getenv("HUGGINGFACE_MODEL") or os.getenv("HF_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")
        
        endpoint_kwargs = {
            "repo_id": model_name,
            "task": "text-generation",
            "max_new_tokens": 1024,
            "temperature": max(temperature, 0.01),
        }
        if api_token:
            endpoint_kwargs["huggingfacehub_api_token"] = api_token
            
        endpoint = HuggingFaceEndpoint(**endpoint_kwargs)
        return ChatHuggingFace(llm=endpoint)
    elif provider in ["google", "gemini"]:
        from langchain_google_genai import ChatGoogleGenerativeAI
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
        model_name = os.getenv("GEMINI_MODEL") or os.getenv("GOOGLE_MODEL", "gemini-1.5-pro")
        
        kwargs = {
            "model": model_name,
            "temperature": temperature
        }
        if api_key:
            kwargs["google_api_key"] = api_key
            
        return ChatGoogleGenerativeAI(**kwargs)
    elif provider == "azure_openai":
        from langchain_openai import AzureChatOpenAI

        # Check AZURE_OPENAI_API_KEY first, then fall back to AZURE_OPENAI_KEY_GPT4o
        api_key = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_KEY_GPT4o", "")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

        if not api_key:
            raise ValueError(
                "Azure OpenAI API key not found. Set it in your terminal session before running, e.g.:\n"
                '  $env:AZURE_OPENAI_API_KEY="<your-key>"\n'
                "(or AZURE_OPENAI_KEY_GPT4o as a fallback name). "
                "Do not hardcode the key or store it in .env."
            )
        if not endpoint:
            raise ValueError(
                "AZURE_OPENAI_ENDPOINT is not set. Add it to your .env file, e.g.:\n"
                "  AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/"
            )

        return AzureChatOpenAI(
            azure_endpoint=endpoint,
            azure_deployment=deployment,
            api_version=api_version,
            api_key=api_key,
            temperature=temperature,
        )
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
        return ChatOpenAI(model=model_name, temperature=temperature)
    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        model_name = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        return ChatAnthropic(model=model_name, temperature=temperature)
    else:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=temperature)