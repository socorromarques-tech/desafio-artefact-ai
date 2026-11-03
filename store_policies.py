import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError


POLICY_PDF_PATH = (
    Path(__file__).resolve().parent / "data" / "políticas_da_loja.pdf"
)
MAX_POLICY_PAGES = 3
STOP_WORDS = {
    "com",
    "como",
    "das",
    "de",
    "do",
    "e",
    "em",
    "manual",
    "na",
    "no",
    "o",
    "para",
    "politica",
    "politicas",
    "qual",
    "quais",
    "sobre",
    "a",
}
POLICY_SEARCH_ALIASES = {
    "endereco": {"rua", "cep", "centro"},
    "horario": {"funcionamento", "expediente"},
    "contato": {"telefone", "whatsapp", "email"},
    "devolucao": {"arrependimento", "reembolso", "recebimento"},
    "troca": {"defeito", "preferencia"},
    "entrega": {"frete", "prazo", "rastreamento"},
    "pagamento": {"pix", "cartao", "boleto", "parcelamento"},
    "garantia": {"fabricante", "defeito"},
    "promocao": {"desconto", "liquidacao"},
    "privacidade": {"lgpd", "dados"},
}


def _normalize_text(value):
    normalized = unicodedata.normalize("NFD", str(value))
    without_accents = "".join(
        char for char in normalized if unicodedata.category(char) != "Mn"
    )
    return re.sub(r"\s+", " ", without_accents).strip().casefold()


def _clean_page_text(value):
    return re.sub(r"\s+", " ", value).strip()


@lru_cache(maxsize=1)
def load_policy_pages():
    """Extrai e armazena em cache o texto das páginas do manual oficial."""
    if not POLICY_PDF_PATH.is_file():
        raise FileNotFoundError(
            f"Manual de políticas não encontrado: {POLICY_PDF_PATH}"
        )

    try:
        reader = PdfReader(str(POLICY_PDF_PATH))
    except PdfReadError as error:
        raise ValueError(
            f"Não foi possível ler o manual de políticas: {POLICY_PDF_PATH}"
        ) from error
    pages = tuple(
        (page_number, _clean_page_text(page.extract_text() or ""))
        for page_number, page in enumerate(reader.pages, start=1)
    )
    pages = tuple((number, text) for number, text in pages if text)
    if not pages:
        raise ValueError(f"Nenhum texto foi extraído de {POLICY_PDF_PATH}")
    return pages


def get_policy_context(theme, pages=None):
    """Retorna as páginas mais relevantes do manual para o tema solicitado."""
    policy_pages = pages if pages is not None else load_policy_pages()
    query_terms = {
        term
        for term in _normalize_text(theme).split()
        if len(term) > 2 and term not in STOP_WORDS
    }
    expanded_terms = set(query_terms)
    for term in query_terms:
        expanded_terms.update(POLICY_SEARCH_ALIASES.get(term, set()))

    if not expanded_terms:
        return "Informe o assunto da política que deseja consultar."

    scored_pages = []
    for page_number, page_text in policy_pages:
        normalized_page = _normalize_text(page_text)
        score = sum(
            len(re.findall(rf"\b{re.escape(term)}\b", normalized_page))
            for term in expanded_terms
        )
        if score:
            scored_pages.append((score, page_number, page_text))

    if not scored_pages:
        return (
            "Não encontrei esse assunto no manual de políticas. "
            "Não informe uma regra sem confirmação da equipe."
        )

    selected_pages = sorted(scored_pages, key=lambda page: (-page[0], page[1]))[
        :MAX_POLICY_PAGES
    ]
    return "\n\n".join(
        f"Trecho do manual (página {page_number}): {page_text}"
        for _, page_number, page_text in sorted(selected_pages, key=lambda page: page[1])
    )
