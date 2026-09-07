"""Comment on présente le Registre et une Retranscription à un modèle.

Le texte destiné au modèle vit ici, et pas dans `registre` : celui-ci est pur, sans LLM et
exhaustivement testable, et doit le rester. Une consigne de prompt qui s'y glisse est une
seconde raison de le modifier.
"""

from minerva.domaine import Retranscription
from minerva.registre import RegistreDItems


def decrire_module(registre: RegistreDItems, module: str) -> str:
    """Les entrées d'un Module, Qualificatif compris, telles qu'un modèle doit les lire."""
    lignes = [
        f"- {item.identifiant} : {item.construct_sonde}"
        for item in registre.items_du_module(module)
    ]
    qualificatif = registre.qualificatif_du_module(module)
    if qualificatif is not None:
        lignes.append(
            f"- {qualificatif.identifiant} : {qualificatif.construct_sonde} "
            "(cadre du module, à établir une seule fois — il vaut pour tous les items "
            "ci-dessus)"
        )
    return "\n".join(lignes)


def decrire_entretien(retranscription: Retranscription) -> str:
    """La Retranscription telle qu'un modèle doit la lire, indices de Tour compris."""
    return "\n".join(
        f"[{tour.indice}] {tour.locuteur.value} : {tour.texte}" for tour in retranscription.tours
    )
