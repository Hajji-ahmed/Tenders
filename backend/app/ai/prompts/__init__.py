"""Prompts versionnés : chaque module expose `PROMPT_VERSION`, `SYSTEM` et un constructeur de message
utilisateur. La version est enregistrée avec les sorties (scores, analyses) pour tracer ce qui a
produit quoi ; on ne modifie jamais un prompt sans incrémenter sa version."""
