"""Lit une Retranscription et un Registre d'items, rend une Fiche.

Un passage de modèle par Module : le modèle voit les Items d'un Module ensemble, ce qui
est le contexte dont il a besoin. La sortie a toujours la forme du Registre, quoi que le
modèle rende — c'est la contrainte de forme qui fait de l'évaluation un diff.
"""

from minerva.domaine import Fiche, Retranscription, VerdictItem
from minerva.modele import PortModele
from minerva.registre import RegistreDItems

_CONSIGNE = """\
Tu analyses la retranscription d'un entretien psychiatrique entre un clinicien et son patient.

Pour chacun des items ci-dessous, dis deux choses indépendantes :
- sollicite : le clinicien a-t-il demandé le contenu de l'item, quelle qu'ait été la réponse ?
- renseigne : l'entretien fournit-il de quoi trancher l'item, que la question ait été posée
  ou que le patient l'ait apporté de lui-même ?

Ces deux propriétés sont indépendantes. Un item peut être renseigné sans avoir été sollicité.

Pour chaque propriété vraie, cite les tours de parole qui l'établissent, par leur indice :
role "sollicitation" pour un tour du clinicien qui pose la question, role "renseignement"
pour un tour du patient qui apporte le contenu. Un même tour peut servir plusieurs items.

Ne cote pas les items et ne pose aucun diagnostic : dis seulement ce que l'entretien couvre.

Items du module {module} :
{items}

Entretien :
{entretien}
"""


def _rendre_entretien(retranscription: Retranscription) -> str:
    return "\n".join(
        f"[{tour.indice}] {tour.locuteur.value} : {tour.texte}" for tour in retranscription.tours
    )


def detecter(
    retranscription: Retranscription, registre: RegistreDItems, modele: PortModele
) -> Fiche:
    """Rend un verdict par Item du Registre, dans l'ordre du Registre.

    Un Item que le modèle n'a pas mentionné est négatif, pas absent. Un identifiant que le
    modèle invente est écarté : le périmètre est celui du Registre, pas celui du modèle.
    """
    verdicts: list[VerdictItem] = []
    for module in registre.modules():
        prompt = _CONSIGNE.format(
            module=module,
            items=registre.decrire_module(module),
            entretien=_rendre_entretien(retranscription),
        )
        rendus = modele.repondre(prompt, Fiche).par_identifiant()
        verdicts.extend(
            rendus.get(item.identifiant) or VerdictItem.negatif(item.identifiant)
            for item in registre.items_du_module(module)
        )
    return Fiche(verdicts=verdicts)
