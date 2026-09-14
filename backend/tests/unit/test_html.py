from app.connectors.html import extract_links, html_to_text


def test_html_to_text_strips_noise_and_keeps_block_breaks():
    html = (
        "<html><head><style>x</style><title>T</title></head><body><nav>menu</nav>"
        "<h1>Appel d'offres</h1><p>Objet : refonte   SI</p><script>1</script>"
        "<footer>pied</footer></body></html>"
    )
    assert html_to_text(html) == "Appel d'offres\nObjet : refonte SI"


def test_html_to_text_handles_inline_tags_and_entities():
    assert html_to_text("<p>Budget : <b>1&nbsp;000</b> MAD &amp; plus</p><br><p></p><div>Fin</div>") == (
        "Budget : 1 000 MAD & plus\nFin"
    )


def test_extract_links_absolutizes_dedupes_and_prefers_same_domain():
    html = """
      <a href="/ao/1">un</a>
      <a href="https://autre.org/x">externe</a>
      <a href="/ao/1#section">doublon (ancre)</a>
      <a href="mailto:contact@portail.ma">mail</a>
      <a href="javascript:void(0)">js</a>
      <a href="dce.pdf">relatif</a>
      <a>sans href</a>
    """
    links = extract_links(html, "https://portail.ma/appels/")
    assert links == ["https://portail.ma/ao/1", "https://portail.ma/appels/dce.pdf", "https://autre.org/x"]
