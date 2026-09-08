"""Le port modèle : l'unique point substituable de MINERVA.

Un prompt et un schéma en entrée, une sortie structurée. L'interface est délibérément
étroite — si une particularité de fournisseur remontait au-dessus, le benchmark cesserait
d'être une comparaison à méthode constante.
"""

from collections.abc import Iterator, Sequence
from typing import Protocol

import anthropic
from pydantic import BaseModel

from minerva.domaine import IdentiteModele


class ReponseIncoherente(RuntimeError):
    """Le modèle a rendu autre chose que le schéma demandé."""


class PortModele(Protocol):
    """Ce que `corpus` et `detection` attendent d'un modèle, et rien de plus."""

    @property
    def identite(self) -> IdentiteModele:
        """Qui répond. C'est le modèle qui se nomme, jamais l'appelant : un nom passé de
        l'extérieur s'étiquette de travers, et la règle de non-contamination reposerait
        alors sur la mémoire du lecteur."""
        ...

    def repondre[T: BaseModel](self, prompt: str, schema: type[T]) -> T: ...


class AdaptateurFactice:
    """Rejoue des sorties structurées écrites d'avance, dans l'ordre.

    C'est ce qui rend la chaîne entière déterministe et hermétique : les tests vérifient
    la mécanique, jamais la qualité de détection — celle-ci relève du benchmark.
    """

    IDENTITE_PAR_DEFAUT = IdentiteModele(nom="factice", famille="factice")

    def __init__(
        self, reponses: Sequence[BaseModel], identite: IdentiteModele | None = None
    ) -> None:
        self._identite = identite or self.IDENTITE_PAR_DEFAUT
        self._reponses: Iterator[BaseModel] = iter(reponses)
        self.prompts: list[str] = []
        """Ce qui a traversé la couture, dans l'ordre — le comportement observable des
        modules appelants, et le seul moyen de vérifier qu'une consigne n'est pas inerte."""

    @property
    def identite(self) -> IdentiteModele:
        return self._identite

    def repondre[T: BaseModel](self, prompt: str, schema: type[T]) -> T:
        self.prompts.append(prompt)
        try:
            reponse = next(self._reponses)
        except StopIteration as fin:
            raise ReponseIncoherente(
                "scénario épuisé : aucune réponse scriptée pour un appel attendant "
                f"{schema.__name__}"
            ) from fin
        if not isinstance(reponse, schema):
            raise ReponseIncoherente(
                f"le scénario rend {type(reponse).__name__} là où {schema.__name__} est attendu"
            )
        return reponse


class AdaptateurAnthropic:
    """Exécute la même chaîne contre un modèle réel, sans que rien au-dessus change.

    Le modèle est un paramètre : c'est ce qui permettra au benchmark de comparer plusieurs
    familles à protocole constant, et de faire respecter la règle de non-contamination.
    """

    MODELE_PAR_DEFAUT = "claude-opus-5"
    FAMILLE = "anthropic"

    def __init__(
        self,
        modele: str = MODELE_PAR_DEFAUT,
        client: anthropic.Anthropic | None = None,
        max_tokens: int = 16000,
    ) -> None:
        self._client = client if client is not None else anthropic.Anthropic()
        self._modele = modele
        self._max_tokens = max_tokens

    @property
    def identite(self) -> IdentiteModele:
        return IdentiteModele(nom=self._modele, famille=self.FAMILLE)

    def repondre[T: BaseModel](self, prompt: str, schema: type[T]) -> T:
        reponse = self._client.beta.messages.parse(
            model=self._modele,
            max_tokens=self._max_tokens,
            thinking={"type": "adaptive"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
        )
        if reponse.stop_reason == "refusal":
            details = getattr(reponse, "stop_details", None)
            categorie = getattr(details, "category", None)
            raise ReponseIncoherente(
                f"le modèle {self._modele} a refusé de répondre (catégorie : {categorie}). "
                "Le contenu clinique de certains modules déclenche les classificateurs de "
                "sécurité ; le repli côté serveur est activé mais n'a pas abouti ici."
            )
        parsee = reponse.parsed_output
        if parsee is None:
            raise ReponseIncoherente(
                f"le modèle {self._modele} n'a rendu aucune sortie conforme à "
                f"{schema.__name__} (stop_reason={reponse.stop_reason})"
            )
        return parsee
