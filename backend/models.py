from pydantic import BaseModel, Field
from typing import List, Optional

class MissionRequest(BaseModel):
    need_description: str = Field(..., description="Description of the exact expertise or need (e.g. 'Solid state battery anodes')")
    sources: List[str] = Field(..., description="List of OSINT sources (e.g., 'arXiv', 'PubMed', 'Patents')")
    min_year: int = Field(2020, description="Minimum publication year to consider")
    extraction_rules: List[str] = Field(..., description="Specific business rules for the LLM to filter articles or authors")
    max_documents: int = Field(100, description="Maximum number of documents to collect")

class Triplet(BaseModel):
    subject: str = Field(..., description="Subject entity name (Usually the Author)")
    subject_type: str = Field("Author", description="Subject entity type/class")
    relation: str = Field(..., description="Relation (e.g. 'AFFILIÉ_À', 'A_POUR_EXPERTISE', 'A_ECRIT')")
    object: str = Field(..., description="Object entity name (Institution, Keyword, or Article title)")
    object_type: str = Field(..., description="Object entity type/class (e.g. 'Institution', 'Skill', 'Article')")
    justification: str = Field(..., description="Quote or reasoning from the abstract to justify this relation")
    confidence: float = Field(..., description="Confidence score from 0.0 to 1.0 based on explicit abstract statement")
    source_url: str = Field(..., description="URL or reference to the origin source (e.g. DOI link)")
    naatbatt_status: Optional[str] = Field(" Not Checked", description="Validation status against NAATBatt database")

class ValidationPayload(BaseModel):
    mission_id: str
    validated_triplets: List[Triplet]

