from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class TelephonyProvider(ABC):
    name: str = "base"
    is_live: bool = False

    @abstractmethod
    async def make_call(
        self,
        customer_name: str,
        phone_number: str,
        campaign_type: str = "acquisition",
        call_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Start an outbound call. Returns {status, call_sid, provider, ...}."""

    @abstractmethod
    async def end_call(self, call_sid: str) -> Dict[str, Any]:
        ...

    async def health(self) -> Dict[str, Any]:
        return {"provider": self.name, "live": self.is_live}
