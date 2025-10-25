from abc import ABC, abstractmethod
from pydantic import BaseModel
from langchain_core.tools import StructuredTool
from typing import Optional, List

class ToolList(BaseModel):
    tools: StructuredTool
    tool_start_message: Optional[str] = None
    tool_end_message: Optional[str] = None
    
class CSToolBase(ABC):
    def __init__(self):
        self.tool_list = []

    @abstractmethod
    def get_tool(self) -> List[ToolList]:
        pass


