"""Découpage du texte extrait en morceaux indexables : coupe aux paragraphes puis aux phrases,
jamais au milieu d'un mot, recouvrement entre morceaux, page d'origine et section conservées."""

from app.services.chunking import Chunk, chunk_pages, detect_section
from app.services.extraction import ExtractedPage


def _sentences(prefix: str, n: int, words: int = 20) -> str:
    return " ".join(
        f"{prefix} phrase {i} " + " ".join(f"mot{j}" for j in range(words)) + "." for i in range(n)
    )


def test_long_text_is_split_below_max_chars_with_overlap_and_page_kept():
    paragraphs = [_sentences("Alpha", 10), _sentences("Bravo", 10), _sentences("Charlie", 11)]
    text = "\n\n".join(paragraphs)
    assert 3_900 <= len(text) <= 4_200

    chunks = chunk_pages([ExtractedPage(number=3, text=text)], max_chars=1500, overlap=200)

    assert len(chunks) >= 3 and all(len(c.text) <= 1500 for c in chunks)
    assert [c.index for c in chunks] == list(range(len(chunks)))
    assert all(c.page == 3 for c in chunks)
    for previous, current in zip(chunks, chunks[1:], strict=False):
        tail = previous.text[-60:]
        assert (
            tail.split()[-1] in current.text[:300]
        )  # recouvrement : la fin du précédent se retrouve au début
        assert not current.text[0].isspace() and not current.text[-1].isspace()
    # Jamais coupé au milieu d'un mot : chaque mot d'un morceau existe tel quel dans le texte.
    words = set(text.split())
    assert all(set(c.text.split()) <= words for c in chunks)
    # Aucune perte : la dernière phrase de chaque paragraphe est bien quelque part.
    joined = " ".join(c.text for c in chunks)
    assert "Alpha phrase 9" in joined and "Bravo phrase 9" in joined and "Charlie phrase 10" in joined


def test_short_pages_give_one_chunk_each_and_empty_pages_none():
    pages = [
        ExtractedPage(number=1, text="Objet du marché."),
        ExtractedPage(number=2, text="   "),
        ExtractedPage(number=3, text="Fin."),
    ]
    chunks = chunk_pages(pages)
    assert [(c.index, c.page, c.text) for c in chunks] == [(0, 1, "Objet du marché."), (1, 3, "Fin.")]


def test_a_sentence_longer_than_max_chars_is_cut_on_whitespace():
    text = " ".join(f"mot{i}" for i in range(400))  # ~2 800 caractères sans ponctuation
    chunks = chunk_pages([ExtractedPage(number=1, text=text)], max_chars=500, overlap=50)
    assert all(len(c.text) <= 500 for c in chunks)
    assert all(c.text.startswith("mot") and c.text.split()[-1].startswith("mot") for c in chunks)
    assert chunks[-1].text.endswith("mot399")


def test_section_headings_are_detected_and_attached_to_following_chunks():
    assert detect_section("Article 3 — Critères d'attribution") == "Article 3 — Critères d'attribution"
    assert detect_section("ARTICLE 12 : DÉLAI D'EXÉCUTION") == "ARTICLE 12 : DÉLAI D'EXÉCUTION"
    assert detect_section("3.2 Conditions de participation") == "3.2 Conditions de participation"
    assert detect_section("CHAPITRE II - Dispositions générales") == "CHAPITRE II - Dispositions générales"
    assert detect_section("Le titulaire doit remettre son offre avant le 20 novembre 2026.") is None
    assert detect_section("3.2 " + "x" * 120) is None  # trop long pour un titre

    text = "Article 1 — Objet\nLe marché porte sur l'éclairage public.\nArticle 2 — Durée\nDouze mois."
    chunks = chunk_pages([ExtractedPage(number=1, text=text)], max_chars=60, overlap=0)
    assert [c.section for c in chunks] == ["Article 1 — Objet", "Article 2 — Durée"]
    assert chunks[0].text.startswith("Article 1 — Objet") and "éclairage" in chunks[0].text
    assert isinstance(chunks[0], Chunk)
