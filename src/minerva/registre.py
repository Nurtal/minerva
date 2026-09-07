"""Le Registre d'items : ce contre quoi MINERVA mesure. Aucun appel de modèle.

Le Registre est reconstruit depuis la littérature publiée et ne contient aucun libellé
d'Item du MINI — voir ADR-0002 et ADR-0003. Chaque entrée cite la source publiée dont
son construct est tiré, ce qui rend la reconstruction auditable sans être refaite.

MINERVA mesure donc la couverture d'un Registre reconstruit aligné sur la structure du
MINI, et non la couverture du MINI.
"""

from pydantic import BaseModel


class Item(BaseModel):
    """Une entrée du Registre : le construct qu'un Item du MINI sonde, et d'où il vient."""

    identifiant: str
    module: str
    construct_sonde: str
    source: str


class RegistreDItems(BaseModel):
    """Les Items connus de MINERVA, groupés par Module."""

    items: list[Item]

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
        ]
    )
