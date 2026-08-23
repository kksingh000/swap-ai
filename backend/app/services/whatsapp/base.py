from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class WhatsAppProvider(ABC):
    name: str = "base"
    is_live: bool = False

    @abstractmethod
    async def send_message(self, to_number: str, body: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    async def send_media(
        self, to_number: str, media_url: str, caption: Optional[str] = None
    ) -> Dict[str, Any]:
        ...

    async def health(self) -> Dict[str, Any]:
        return {"provider": self.name, "live": self.is_live}
