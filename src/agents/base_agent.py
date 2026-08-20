"""Base agent abstraction with configuration management, structured LLM invocation, and logging."""

from __future__ import annotations
import os
import yaml
from pathlib import Path
from typing import Any, Type, TypeVar
from pydantic import BaseModel
from dotenv import load_dotenv

from src.utils.logger import get_logger

load_dotenv()

T = TypeVar("T", bound=BaseModel)


class BaseAgent:
    """Base class for all modernization pipeline agents."""

    def __init__(self, agent_name: str, config_dir: str | Path = "configs"):
        self.agent_name = agent_name
        self.logger = get_logger(f"Agent.{agent_name}")
        self.config_dir = Path(config_dir)
        self.llm_config = self._load_yaml(self.config_dir / "llm_config.yaml")
        self.thresholds = self._load_yaml(self.config_dir / "thresholds.yaml")
        self.agents_config = self._load_yaml(self.config_dir / "agents.yaml")
        
        self.provider = os.getenv("LLM_PROVIDER", self.llm_config.get("default", {}).get("provider", "mock")).lower()
        self.model_name = self._get_agent_setting("model", "gpt-4o")
        self.temperature = float(self._get_agent_setting("temperature", 0.1))
        
        self._llm = None
        self._init_llm()
        self.logger.debug("Initialized %s with provider=%s, model=%s, temp=%s", self.agent_name, self.provider, self.model_name, self.temperature)

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        """Loads a YAML configuration file safely."""
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                self.logger.warning("Failed to parse YAML file at %s: %s", path, e)
                return {}
        return {}

    def _get_agent_setting(self, key: str, default: Any) -> Any:
        """Retrieves an agent-specific setting, falling back to default."""
        agent_overrides = self.llm_config.get("agents", {}).get(self.agent_name, {})
        if key in agent_overrides:
            return agent_overrides[key]
        return self.llm_config.get("default", {}).get(key, default)

    def _init_llm(self):
        """Initializes the underlying LangChain chat model if API keys exist."""
        if self.provider == "openai":
            if os.getenv("AZURE_OPENAI_KEY_GPT4o"):
                try:
                    from langchain_openai import AzureChatOpenAI
                    self._llm = AzureChatOpenAI(
                        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", self.model_name),
                        api_version="2025-01-01-preview",
                        temperature=self.temperature,
                        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                        api_key=os.getenv("AZURE_OPENAI_KEY_GPT4o")
                    )
                    self.logger.info("AzureChatOpenAI client initialized for %s", self.agent_name)
                except Exception as e:
                    self.logger.warning("Failed to initialize AzureChatOpenAI: %s. Falling back to mock.", e)
                    self._llm = None
            elif os.getenv("OPENAI_API_KEY"):
                try:
                    from langchain_openai import ChatOpenAI
                    self._llm = ChatOpenAI(
                        model=self.model_name,
                        temperature=self.temperature,
                        api_key=os.getenv("OPENAI_API_KEY")
                    )
                    self.logger.info("ChatOpenAI client initialized for %s", self.agent_name)
                except Exception as e:
                    self.logger.warning("Failed to initialize ChatOpenAI: %s. Falling back to mock.", e)
                    self._llm = None
            else:
                self._llm = None
        elif self.provider == "anthropic" and os.getenv("ANTHROPIC_API_KEY"):
            try:
                from langchain_anthropic import ChatAnthropic
                self._llm = ChatAnthropic(
                    model_name=self.model_name,
                    temperature=self.temperature,
                    api_key=os.getenv("ANTHROPIC_API_KEY")
                )
                self.logger.info("ChatAnthropic client initialized for %s", self.agent_name)
            except Exception as e:
                self.logger.warning("Failed to initialize ChatAnthropic: %s. Falling back to mock.", e)
                self._llm = None
        else:
            self._llm = None

    def invoke_structured(
        self,
        schema: Type[T],
        system_prompt: str,
        user_prompt: str,
        mock_fallback_generator: Any = None
    ) -> T:
        """Invokes the LLM with structured output, or falls back to deterministic generator."""
        if self._llm is not None:
            try:
                self.logger.debug("[%s] Invoking LLM with structured schema %s", self.agent_name, schema.__name__)
                structured_llm = self._llm.with_structured_output(schema)
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
                res = structured_llm.invoke(messages)
                if isinstance(res, schema):
                    self.logger.info("[%s] Received structured response via %s", self.agent_name, self.provider)
                    return res
                elif isinstance(res, dict):
                    return schema.model_validate(res)
            except Exception as e:
                self.logger.warning("[%s] Structured LLM call failed (%s). Falling back to mock generator.", self.agent_name, e)

        # Deterministic offline mock generator
        if mock_fallback_generator:
            self.logger.debug("[%s] Using deterministic mock fallback generator for %s", self.agent_name, schema.__name__)
            return mock_fallback_generator()
        
        self.logger.error("[%s] No active LLM provider and no mock generator for %s", self.agent_name, schema.__name__)
        raise RuntimeError(f"No active LLM provider and no mock generator for {self.agent_name}")
