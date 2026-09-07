"""Tire une Spécification et en dérive un Entretien. La vérité terrain est vraie par construction.

On ne génère pas un Entretien qu'on annote ensuite : on fixe d'abord ce que l'Entretien
devra contenir, puis on le fait écrire. Encore faut-il vérifier que le modèle a réalisé la
commande — un corpus dont la référence ment produit des chiffres faux, ce qui est pire
qu'un corpus absent. C'est ce que fait `_verifier`, et c'est ce qui rend « vraie par
construction » autre chose qu'un vœu.

Un Entretien est **une** conversation : il se génère en un seul passage, tous Modules
confondus. Générer Module par Module puis recoller donnerait des indices de Tour dupliqués
et des Empans pointant sur les Tours d'un autre Module.
"""

from pydantic import BaseModel

from minerva.domaine import Entretien, Fiche, Propriete, Retranscription, VerdictItem
from minerva.modele import PortModele
from minerva.registre import RegistreDItems


class GenerationInfidele(RuntimeError):
    """L'Entretien produit ne réalise pas la Spécification qui l'a commandé."""


class Specification(BaseModel):
    """Ce qu'un Entretien devra contenir, avant qu'il existe.

    Porte une Fiche, du même type que celle rendue par la détection : c'est la contrainte
    de forme qui fait de l'évaluation un diff plutôt qu'une traduction. Seuls les deux
    booléens de chaque verdict sont lus — les Empans de preuve n'existent pas encore à ce
    stade, ils naissent avec l'Entretien.
    """

    fiche_visee: Fiche


_CONSIGNE = """\
Écris la retranscription plausible d'un entretien psychiatrique en français entre un
clinicien et son patient, puis dis quels tours de parole réalisent quel item.

C'est un seul entretien continu, même s'il couvre plusieurs modules. Numérote les tours
à partir de zéro, dans l'ordre, sans doublon, et attribue chacun au clinicien ou au patient.

L'entretien doit réaliser exactement la commande suivante, item par item :
{commande}

Rappels :
- sollicite signifie que le clinicien pose la question, quelle que soit la réponse ;
- renseigne signifie que l'entretien donne de quoi trancher l'item, que la question ait
  été posée ou que le patient l'ait apporté de lui-même ;
- un item peut être renseigné sans avoir été sollicité, et sollicité sans être renseigné.

Pour chaque propriété vraie, cite les tours qui l'établissent par leur indice : role
"sollicitation" pour un tour du clinicien, "renseignement" pour un tour du patient.

Items :
{items}
"""


def _rendre_commande(specification: Specification, registre: RegistreDItems) -> str:
    vises = specification.fiche_visee.par_identifiant()
    return "\n".join(
        f"- {ident} : sollicite={vises[ident].sollicite}, renseigne={vises[ident].renseigne}"
        for ident in registre.identifiants()
    )


def _rendre_items(registre: RegistreDItems) -> str:
    return "\n".join(
        f"{module} :\n{registre.decrire_module(module)}" for module in registre.modules()
    )


def _verifier_couverture(specification: Specification, registre: RegistreDItems) -> None:
    """Une Spécification doit viser chaque Item du Registre.

    Un Item absent n'est pas un Item non visé, c'est une commande trouée.
    """
    vises = specification.fiche_visee.identifiants()
    manquants = [ident for ident in registre.identifiants() if ident not in vises]
    if manquants:
        raise GenerationInfidele(
            f"la spécification ne vise pas {', '.join(manquants)} — un Item absent n'est pas "
            "un Item non visé, c'est une commande incomplète"
        )


def _verifier_retranscription(retranscription: Retranscription) -> None:
    indices = [tour.indice for tour in retranscription.tours]
    if indices != sorted(set(indices)):
        raise GenerationInfidele(
            f"les indices de tour doivent être uniques et ordonnés, obtenu {indices}"
        )


def _verifier(produit: Entretien, specification: Specification, registre: RegistreDItems) -> Fiche:
    """Vérifie que l'Entretien réalise la commande, et rend la Fiche de référence."""
    _verifier_retranscription(produit.retranscription)

    locuteur_du_tour = {tour.indice: tour.locuteur for tour in produit.retranscription.tours}
    vises = specification.fiche_visee.par_identifiant()
    rendus = produit.reference.par_identifiant()
    reference: list[VerdictItem] = []

    for identifiant in registre.identifiants():
        attendu = vises[identifiant]
        obtenu = rendus.get(identifiant) or VerdictItem.negatif(identifiant)

        for propriete in Propriete:
            if obtenu.porte(propriete) != attendu.porte(propriete):
                raise GenerationInfidele(
                    f"{identifiant} : {propriete.value} commandé à {attendu.porte(propriete)}, "
                    f"obtenu {obtenu.porte(propriete)}"
                )
            if obtenu.porte(propriete) and not obtenu.empans_de(propriete.role):
                raise GenerationInfidele(
                    f"{identifiant} : {propriete.value} est vrai sans aucun empan de "
                    f"{propriete.role.value} ; une référence qui affirme sans montrer n'est "
                    "pas une vérité terrain"
                )

        for empan in obtenu.empans:
            locuteur = locuteur_du_tour.get(empan.indice_tour)
            if locuteur is None:
                raise GenerationInfidele(
                    f"{identifiant} : empan sur le tour {empan.indice_tour}, qui n'existe pas"
                )
            if locuteur is not empan.role.locuteur:
                raise GenerationInfidele(
                    f"{identifiant} : empan de {empan.role.value} sur le tour "
                    f"{empan.indice_tour}, qui est un tour du {locuteur.value}"
                )

        reference.append(obtenu)

    return Fiche(verdicts=reference)


def generer(
    specification: Specification, registre: RegistreDItems, modele: PortModele
) -> Entretien:
    """Dérive un Entretien de la Spécification, et refuse celui qui ne la réalise pas."""
    _verifier_couverture(specification, registre)
    prompt = _CONSIGNE.format(
        commande=_rendre_commande(specification, registre),
        items=_rendre_items(registre),
    )
    produit = modele.repondre(prompt, Entretien)
    return Entretien(
        retranscription=produit.retranscription,
        reference=_verifier(produit, specification, registre),
    )
