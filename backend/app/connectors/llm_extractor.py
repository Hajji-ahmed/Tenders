"""Extracteur d'appels d'offres par LLM : page crawlée → `TenderCandidate` (prompt `tender_extract`).
`None` si la page est illisible, n'est pas un appel d'offres ou si la confiance est trop faible.
Les erreurs du modèle remontent : la collecte (3.5) les rapporte par source."""

from urllib.parse import urljoin

from app.ai.llm import LLMProvider
from app.ai.outputs import TenderCandidate
from app.ai.prompts import tender_extract
from app.connectors.crawl.base import CrawlResult


class LLMTenderExtractor:
    prompt_version = tender_extract.PROMPT_VERSION

    def __init__(self, llm: LLMProvider, *, min_confidence: float = 0.6, max_chars: int = 12_000):
        self._llm = llm
        self.min_confidence = min_confidence
        self.max_chars = max_chars

    def extract(self, page: CrawlResult) -> TenderCandidate | None:
        if not page.ok or not page.text.strip():
            return None  # rien à lire : pas d'appel au modèle
        candidate = self._llm.structured(
            system=tender_extract.SYSTEM,
            user=tender_extract.user_prompt(page, max_chars=self.max_chars),
            output=TenderCandidate,
            tier="fast",
        )
        if not candidate.is_tender or candidate.confidence < self.min_confidence:
            return None
        candidate.source_url = page.url
        # Le modèle recopie les liens tels quels ; on garantit des URL absolues et dédupliquées.
        candidate.document_urls = list(
            dict.fromkeys(urljoin(page.url, u) for u in candidate.document_urls if u)
        )
        return candidate
