"""
Data Provider Registry

Manages registration and access to data providers.
Supports multi-domain provider routing.
"""

from __future__ import annotations

from typing import Optional
import logging

from ai_trading_tool.core.data.base import (
    DataProvider,
    DataDomain,
)
from ai_trading_tool.core.data.providers import (
    YahooFinanceProvider,
    CSVProvider,
)

logger = logging.getLogger(__name__)


class DataProviderRegistry:
    """
    Registry for data providers.
    
    Singleton pattern - use get_instance() to access.
    Supports routing by data domain.
    """
    
    _instance: Optional[DataProviderRegistry] = None
    
    def __init__(self):
        self._providers: dict[str, DataProvider] = {}
        self._domain_providers: dict[DataDomain, list[str]] = {
            domain: [] for domain in DataDomain
        }
        self._default: Optional[str] = None
    
    @classmethod
    def get_instance(cls) -> DataProviderRegistry:
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def register(
        self,
        name: str,
        provider: DataProvider,
        set_default: bool = False,
    ) -> None:
        """
        Register a data provider.
        
        Args:
            name: Provider name
            provider: DataProvider instance
            set_default: Set as default provider
        """
        self._providers[name] = provider
        
        # Register by domain
        for domain in provider.supported_domains:
            if name not in self._domain_providers[domain]:
                self._domain_providers[domain].append(name)
        
        if set_default or not self._default:
            self._default = name
        
        logger.info(
            "Registered data provider",
            provider=name,
            domains=[d.value for d in provider.supported_domains],
        )
    
    def get(self, name: Optional[str] = None) -> DataProvider:
        """
        Get a registered provider.
        
        Args:
            name: Provider name, or None for default
        
        Returns:
            DataProvider instance
        
        Raises:
            KeyError: If provider not found
        """
        if name is None:
            name = self._default
        
        if name not in self._providers:
            raise KeyError(f"Provider not found: {name}")
        
        return self._providers[name]
    
    def get_for_domain(
        self,
        domain: DataDomain,
        name: Optional[str] = None,
    ) -> DataProvider:
        """
        Get a provider that supports a specific domain.
        
        Args:
            domain: Data domain to support
            name: Specific provider name, or None for first available
        
        Returns:
            DataProvider instance
        """
        if name:
            provider = self.get(name)
            if domain not in provider.supported_domains:
                raise ValueError(
                    f"Provider {name} does not support domain {domain.value}"
                )
            return provider
        
        # Get first provider for domain
        domain_providers = self._domain_providers.get(domain, [])
        if not domain_providers:
            raise KeyError(f"No provider registered for domain: {domain.value}")
        
        return self.get(domain_providers[0])
    
    def list_for_domain(self, domain: DataDomain) -> list[str]:
        """List all providers that support a domain."""
        return self._domain_providers.get(domain, [])
    
    def unregister(self, name: str) -> None:
        """Unregister a provider."""
        if name in self._providers:
            provider = self._providers[name]
            
            # Remove from domain mappings
            for domain in provider.supported_domains:
                if name in self._domain_providers[domain]:
                    self._domain_providers[domain].remove(name)
            
            del self._providers[name]
            
            if self._default == name:
                self._default = next(iter(self._providers), None)
            
            logger.info("Unregistered data provider", provider=name)
    
    def list_providers(self) -> list[str]:
        """List all registered provider names."""
        return list(self._providers.keys())
    
    def list_domains(self) -> list[DataDomain]:
        """List all domains with registered providers."""
        return [
            domain for domain, providers in self._domain_providers.items()
            if providers
        ]
    
    @property
    def default(self) -> Optional[DataProvider]:
        """Get the default provider."""
        if self._default:
            return self._providers.get(self._default)
        return None
    
    async def initialize_defaults(self) -> None:
        """
        Initialize default providers.
        
        Call this during application startup.
        """
        # Register Yahoo Finance (market data + fundamentals)
        try:
            yf_provider = YahooFinanceProvider()
            await yf_provider.connect()
            self.register("yfinance", yf_provider, set_default=True)
        except Exception as e:
            logger.error("Failed to initialize yfinance provider", error=str(e))
        
        logger.info("Initialized default data providers")
    
    async def shutdown(self) -> None:
        """Disconnect all providers."""
        for name, provider in self._providers.items():
            try:
                await provider.disconnect()
            except Exception as e:
                logger.error(
                    "Failed to disconnect provider",
                    provider=name,
                    error=str(e),
                )
        
        self._providers.clear()
        self._default = None
        
        for domain in self._domain_providers:
            self._domain_providers[domain] = []


# Convenience functions
def get_provider(name: Optional[str] = None) -> DataProvider:
    """Get a data provider."""
    return DataProviderRegistry.get_instance().get(name)


def get_provider_for_domain(
    domain: DataDomain,
    name: Optional[str] = None,
) -> DataProvider:
    """Get a provider for a specific domain."""
    return DataProviderRegistry.get_instance().get_for_domain(domain, name)


def register_provider(
    name: str,
    provider: DataProvider,
    set_default: bool = False,
) -> None:
    """Register a data provider."""
    DataProviderRegistry.get_instance().register(name, provider, set_default)


__all__ = [
    "DataProviderRegistry",
    "get_provider",
    "get_provider_for_domain",
    "register_provider",
]
