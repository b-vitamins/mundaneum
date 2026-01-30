from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class S2Author(BaseModel):
    authorId: Optional[str] = None
    name: Optional[str] = None


class S2TLDR(BaseModel):
    model: str
    text: str


class S2Embedding(BaseModel):
    model: str
    vector: List[float]


class S2Paper(BaseModel):
    paperId: str
    title: Optional[str] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    authors: List[S2Author] = []
    abstract: Optional[str] = None
    tldr: Optional[S2TLDR] = None
    embedding: Optional[S2Embedding] = None
    citationCount: int = 0
    referenceCount: int = 0
    influentialCitationCount: int = 0
    isOpenAccess: bool = False
    openAccessPdf: Optional[Dict[str, Any]] = None
    fieldsOfStudy: List[str] = []
    publicationTypes: List[str] = []
    externalIds: Dict[str, str] = {}

    # For graph edges
    contexts: List[str] = []
    intents: List[str] = []
    isInfluential: bool = False


class S2GraphEdge(BaseModel):
    """Represents an edge in the graph response (citation or reference)."""

    contexts: List[str] = []
    intents: List[str] = []
    isInfluential: bool = False
    citedPaper: Optional[S2Paper] = None
    citingPaper: Optional[S2Paper] = None


class S2GraphResponse(BaseModel):
    data: List[S2GraphEdge] = []
    next: Optional[int] = None
    offset: Optional[int] = None
