from typing import List, Optional
from pydantic import BaseModel, Field

class SectionCopy(BaseModel):
    header: str = Field(description="Title or header for the section")
    content: str = Field(description="1 to 2 paragraphs of compelling copywriter text")

class PageCopyResponse(BaseModel):
    page_title: str
    is_vehicle_specific: bool
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    sections: List[SectionCopy] = Field(description="List of maximum 5 sections with header and content")