from dataclasses import dataclass


@dataclass
class RetrievedDoc:
    id: str
    source: str
    title: str
    content: str
