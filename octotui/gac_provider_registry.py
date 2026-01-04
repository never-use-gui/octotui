"""GAC provider registry - extracts providers from GAC at runtime."""

import logging
import re
from typing import Dict, Tuple, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import from GAC
try:
    import gac
    from gac import model_cli

    GAC_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    GAC_AVAILABLE = False
    gac = None  # type: ignore
    model_cli = None  # type: ignore


def _extract_providers_from_gac() -> Optional[Dict[str, Tuple[str, str]]]:
    """Extract provider list from GAC's model_cli module by reading source file.

    Returns:
        Dict mapping provider_key -> (display_name, default_model), or None if extraction fails
    """
    if not GAC_AVAILABLE or model_cli is None:
        return None

    try:
        # Get the module file path
        module_file = Path(model_cli.__file__)
        if not module_file.exists():
            logger.debug(f"GAC model_cli file not found: {module_file}")
            return None

        # Read the source file
        source = module_file.read_text(encoding="utf-8")

        # Find the providers list in _configure_model function
        # Pattern: providers = [ ... ("Name", "model"), ... ]
        # Use bracket-counting to handle nested brackets (e.g., list comprehensions)
        start_match = re.search(r"providers\s*=\s*\[", source)
        if not start_match:
            logger.debug("Could not find providers list in GAC's model_cli")
            return None

        # Find the matching closing bracket by counting brackets
        start_pos = start_match.end()
        bracket_count = 1
        pos = start_pos

        while pos < len(source) and bracket_count > 0:
            if source[pos] == "[":
                bracket_count += 1
            elif source[pos] == "]":
                bracket_count -= 1
            pos += 1

        if bracket_count != 0:
            logger.debug("Could not find matching closing bracket for providers list")
            return None

        providers_text = source[start_pos : pos - 1]

        # Parse tuples: ("Display Name", "model")
        tuple_pattern = r'\("([^"]+)",\s*"([^"]*)"\)'
        matches = re.findall(tuple_pattern, providers_text)

        if not matches:
            logger.debug("Could not parse provider tuples from GAC")
            return None

        # Convert to our format: provider_key -> (display_name, default_model)
        result = {}
        for display_name, default_model in matches:
            # Generate provider key using GAC's logic (from model_cli.py)
            provider_key = (
                display_name.lower()
                .replace(".", "")
                .replace(" ", "-")
                .replace("(", "")
                .replace(")", "")
            )
            
            # Apply GAC's provider key normalization
            if provider_key == "claude-code-oauth":
                provider_key = "claude-code"
            elif provider_key == "kimi-for-coding":
                provider_key = "kimi-coding"
            elif provider_key == "minimaxio":
                provider_key = "minimax"
            elif provider_key == "moonshot-ai":
                provider_key = "moonshot"
            elif provider_key == "qwenai-oauth":
                provider_key = "qwen"
            elif provider_key == "syntheticnew":
                provider_key = "synthetic"
            
            result[provider_key] = (display_name, default_model)

        logger.debug(f"Successfully extracted {len(result)} providers from GAC")
        return result

    except Exception as e:
        logger.debug(f"Failed to extract providers from GAC: {e}")
        return None


class GACProviderRegistry:
    """Registry for GAC AI providers - extracts from GAC at runtime."""

    # Cache for extracted providers
    _cached_providers: Optional[Dict[str, Tuple[str, str]]] = None

    @classmethod
    def get_supported_providers(cls) -> Dict[str, Tuple[str, str]]:
        """Get dictionary of supported providers from GAC.

        Returns:
            Dict mapping provider_key -> (display_name, default_model)
        """
        # Use cache if available
        if cls._cached_providers is not None:
            return cls._cached_providers.copy()

        # Try to extract from GAC
        if GAC_AVAILABLE:
            providers = _extract_providers_from_gac()
            if providers:
                cls._cached_providers = providers
                logger.info(f"Loaded {len(providers)} providers from GAC")
                return providers.copy()

        # Fallback: return empty dict with warning
        logger.warning(
            "Could not load providers from GAC - GAC may not be installed or provider extraction failed. Provider list will be empty."
        )
        return {}

    @classmethod
    def get_suggested_models(cls, provider: str) -> list[str]:
        """Get list of suggested models for a provider.

        Args:
            provider: Provider key (e.g., "anthropic", "openai")

        Returns:
            List of suggested model names
        """
        providers = cls.get_supported_providers()
        if provider not in providers:
            return []

        _, default_model = providers[provider]
        if not default_model:
            return []

        return [default_model]

    @classmethod
    def get_default_model(cls, provider: str) -> str:
        """Get the default model for a provider.

        Args:
            provider: Provider key

        Returns:
            Default model name, or empty string if none
        """
        providers = cls.get_supported_providers()
        if provider not in providers:
            return ""

        _, default_model = providers[provider]
        return default_model

    @classmethod
    def is_local_provider(cls, provider: str) -> bool:
        """Check if provider is local (no API key needed).

        Args:
            provider: Provider key

        Returns:
            True if local provider
        """
        return provider in ("ollama", "lm-studio")

    @classmethod
    def validate_model_format(cls, model: str) -> Tuple[bool, str]:
        """Validate model string format.

        Args:
            model: Full model string (provider:model)

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not model:
            return False, "Model cannot be empty"

        if ":" not in model:
            return False, "Model must be in format 'provider:model'"

        provider, model_name = model.split(":", 1)

        if not provider.strip():
            return False, "Provider name cannot be empty"
        if not model_name.strip():
            return False, "Model name cannot be empty"

        return True, ""
