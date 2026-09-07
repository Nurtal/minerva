"""Le Registre d'items : ce contre quoi MINERVA mesure. Aucun appel de modèle.

Le Registre est reconstruit depuis la littérature publiée et ne contient aucun libellé
d'Item du MINI — voir ADR-0002 et ADR-0003. Chaque entrée cite la source publiée dont
son construct est tiré, ce qui rend la reconstruction auditable sans être refaite.

MINERVA mesure donc la couverture d'un Registre reconstruit aligné sur la structure du
MINI, et non la couverture du MINI.
"""

from collections.abc import Mapping

from pydantic import BaseModel, Field, model_validator

from minerva.domaine import Polarite


class Porte(BaseModel):
    """Au moins `au_moins` opérandes vrais parmi `parmi`.

    Cette forme unique couvre les trois shapes du MINI : un ET est `au_moins` égal au
    nombre d'opérandes, un OU est `au_moins` à un, et un comptage — « deux réponses ou
    plus cotées oui » — est le cas général. Les opérandes sont des identifiants d'Item
    ou des sous-conditions, ce qui permet les portes imbriquées du type
    (G1a ET G1b ET G2) OU (G3a ET G3b).
    """

    au_moins: int = Field(ge=1)
    parmi: list["str | Porte"]
    source: str | None = None
    """La source publiée dont cette porte est tirée — ADR-0003.

    Renseignée pour une porte du Registre, absente pour une sous-porte, qui n'est pas
    une entrée mais un morceau de la porte qui la contient.
    """

    @model_validator(mode="after")
    def _verifier_atteignable(self) -> "Porte":
        if self.au_moins > len(self.parmi):
            raise ValueError(
                f"porte inatteignable : {self.au_moins} opérandes vrais exigés parmi "
                f"{len(self.parmi)} — elle serait toujours fausse"
            )
        return self

    def identifiants(self) -> set[str]:
        """Les Items dont cette porte a besoin — ceux dont la polarité doit être connue."""
        besoins: set[str] = set()
        for operande in self.parmi:
            if isinstance(operande, str):
                besoins.add(operande)
            else:
                besoins |= operande.identifiants()
        return besoins

    def evaluer(self, polarites: Mapping[str, Polarite]) -> Polarite:
        """Évalue la porte en logique à trois valeurs.

        Une polarité inconnue ne vaut pas faux. La porte n'est fausse que si aucune
        complétion des inconnues ne pourrait l'atteindre — sans quoi un filtre jamais
        établi excuserait ce qui le suit, et la mesure récompenserait le fait de ne rien
        demander.
        """
        vrais = indetermines = 0
        for operande in self.parmi:
            valeur = (
                polarites.get(operande)
                if isinstance(operande, str)
                else operande.evaluer(polarites)
            )
            if valeur is True:
                vrais += 1
            elif valeur is None:
                indetermines += 1

        if vrais >= self.au_moins:
            return True
        if vrais + indetermines < self.au_moins:
            return False
        return None


Porte.model_rebuild()


class Item(BaseModel):
    """Une entrée du Registre : le construct qu'un Item du MINI sonde, et d'où il vient."""

    identifiant: str
    module: str
    construct_sonde: str
    source: str
    porte: Porte | None = None
    """Porte du second étage : ce qui doit être vrai pour que cet Item soit attendu."""


class RegistreDItems(BaseModel):
    """Les Items connus de MINERVA, groupés par Module."""

    items: list[Item]
    portes_de_module: dict[str, Porte] = {}
    """Portes du premier étage : le filtre en tête de chaque Module qui en a un."""

    def modules(self) -> list[str]:
        vus: list[str] = []
        for item in self.items:
            if item.module not in vus:
                vus.append(item.module)
        return vus

    def items_du_module(self, module: str) -> list[Item]:
        return [item for item in self.items if item.module == module]

    def identifiants(self) -> list[str]:
        return [item.identifiant for item in self.items]

    def items_filtres(self) -> set[str]:
        """Les Items dont le graphe a besoin de la polarité, et eux seuls.

        C'est la portée exacte de l'exception posée par ADR-0006 : hors de cet ensemble,
        MINERVA ne code rien.
        """
        besoins: set[str] = set()
        for porte in self.portes_de_module.values():
            besoins |= porte.identifiants()
        for item in self.items:
            if item.porte is not None:
                besoins |= item.porte.identifiants()
        return besoins

    def non_applicables(self, polarites: Mapping[str, Polarite]) -> set[str]:
        """Les Items que la logique de saut écarte légitimement.

        Un Item n'est écarté que par une porte **établie et négative**. Une porte
        indéterminée ne l'écarte pas : le Clinicien avait le devoir de l'établir, et
        l'excuser reviendrait à récompenser l'entretien qui ne demande rien.

        Un Item qui sert lui-même de filtre à son Module n'est jamais écarté par ce
        filtre — c'est la question d'entrée, elle est toujours attendue.
        """
        modules_fermes = {
            module: porte.identifiants()
            for module, porte in self.portes_de_module.items()
            if porte.evaluer(polarites) is False
        }
        return {
            item.identifiant
            for item in self.items
            if (
                item.module in modules_fermes
                and item.identifiant not in modules_fermes[item.module]
            )
            or (item.porte is not None and item.porte.evaluer(polarites) is False)
        }

    def decrire_module(self, module: str) -> str:
        """Les Items d'un Module tels qu'on les présente à un modèle."""
        return "\n".join(
            f"- {item.identifiant} : {item.construct_sonde}"
            for item in self.items_du_module(module)
        )


def registre_module_a_reduit() -> RegistreDItems:
    """Trois Items du Module A, le strict nécessaire au tracer bullet.

    Le Module A complet — ses six Items et leurs quinze questions cotées — relève d'un
    ticket dédié, avec double reconstruction et contrôle croisé contre le PHQ-9.
    """
    return RegistreDItems(
        portes_de_module={
            # Le filtre en tête du Module A : humeur dépressive OU perte d'intérêt.
            # Établi négatif sur les deux, le reste du Module est légitimement écarté.
            "A": Porte(
                au_moins=1,
                parmi=["A1", "A2"],
                source="APA, DSM-5-TR (2022) : l'épisode dépressif caractérisé requiert "
                "l'humeur dépressive ou la perte d'intérêt ; structure de la question de "
                "filtre en tête de module.",
            ),
        },
        items=[
            Item(
                identifiant="A1",
                module="A",
                construct_sonde=(
                    "Humeur dépressive présente la majeure partie de la journée, presque tous "
                    "les jours, depuis au moins deux semaines."
                ),
                source="APA, DSM-5-TR (2022), critère A1 de l'épisode dépressif caractérisé ; "
                "recoupé par le PHQ-9 item 2 (Kroenke, Spitzer & Williams, 2001).",
            ),
            Item(
                identifiant="A2",
                module="A",
                construct_sonde=(
                    "Diminution marquée de l'intérêt ou du plaisir pour toutes ou presque "
                    "toutes les activités, sur la même période."
                ),
                source="APA, DSM-5-TR (2022), critère A2 de l'épisode dépressif caractérisé ; "
                "recoupé par le PHQ-9 item 1 (Kroenke, Spitzer & Williams, 2001).",
            ),
            Item(
                identifiant="A3a",
                module="A",
                construct_sonde=(
                    "Insomnie ou hypersomnie presque tous les jours sur la même période."
                ),
                source="APA, DSM-5-TR (2022), critère A4 de l'épisode dépressif caractérisé ; "
                "recoupé par le PHQ-9 item 3 (Kroenke, Spitzer & Williams, 2001).",
            ),
        ],
    )
