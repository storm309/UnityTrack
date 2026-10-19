from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class DataSource(ABC):
    """Abstract interface for railway data sources (synthetic or external TMS/SMMS/TDMS)."""

    @abstractmethod
    def get_corridors(self) -> List[Dict[str, Any]]:
        """Return list of corridors."""
        pass

    @abstractmethod
    def get_sections(self, corridor_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return list of sections, optionally filtered by corridor_id."""
        pass

    @abstractmethod
    def get_tasks(
        self,
        department: Optional[str] = None,
        section_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return list of maintenance tasks, optionally filtered."""
        pass

    @abstractmethod
    def get_train_slots(
        self,
        corridor_id: Optional[str] = None,
        section_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return list of train timetable slots, optionally filtered."""
        pass

    @abstractmethod
    def get_resources(self) -> List[Dict[str, Any]]:
        """Return list of departmental crew capacities."""
        pass

    @abstractmethod
    def get_block_windows(
        self,
        section_id: Optional[str] = None,
        is_night_window: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """Return list of allowable maintenance block windows derived from timetable gaps."""
        pass
