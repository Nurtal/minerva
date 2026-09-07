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

from enum import StrEnum

from pydantic import BaseModel

from minerva.domaine import (
    Entretien,
    Fiche,
    Propriete,
    Retranscription,
    Style,
    VerdictItem,
)
from minerva.modele import PortModele
from minerva.registre import RegistreDItems
from minerva.rendu import decrire_module


class GenerationInfidele(RuntimeError):
    """L'Entretien produit ne réalise pas la Spécification qui l'a commandé."""


class NaturePhenomene(StrEnum):
    """Les difficultés qu'un Corpus doit éprouver, faute de quoi il n'éprouve rien.

    Quatre d'entre elles impliquent définitionnellement un état visé ; la cinquième
    porte sur un Module et se vérifie contre son graphe de saut.
    """

    SANS_REPONSE = "sans_reponse"
    """Le Clinicien pose la question, le Patient n'apporte rien d'exploitable."""
    APPORT_SPONTANE = "apport_spontane"
    """Le Patient apporte le contenu sans qu'on le lui ait demandé."""
    FAUX_AMI = "faux_ami"
    """L'Entretien contient un contenu qui ressemble à l'Item sans en être."""
    NEGATION = "negation"
    """La réponse est explicitement négative — ce qui renseigne l'Item, et ne l'annule pas."""
    MODULE_SAUTE = "module_saute"
    """Le filtre d'un Module est établi négatif et la suite du Module est écartée à raison."""


class PhenomeneAdverse(BaseModel):
    """Une difficulté imposée à la génération, rattachée à ce qu'elle vise.

    La cible est l'identifiant d'une entrée du Registre, sauf pour MODULE_SAUTE où elle
    nomme un Module.
    """

    nature: NaturePhenomene
    cible: str


_ETATS_IMPLIQUES: dict[NaturePhenomene, tuple[bool | None, bool | None]] = {
    NaturePhenomene.SANS_REPONSE: (True, False),
    NaturePhenomene.APPORT_SPONTANE: (False, True),
    NaturePhenomene.NEGATION: (None, True),
    NaturePhenomene.FAUX_AMI: (None, False),
}
"""Ce que chaque nature impose de (sollicite, renseigne). None : la nature ne dit rien."""


class Specification(BaseModel):
    """Ce qu'un Entretien devra contenir, avant qu'il existe.

    Porte une Fiche, du même type que celle rendue par la détection : c'est la contrainte
    de forme qui fait de l'évaluation un diff plutôt qu'une traduction. Seuls les deux
    booléens de chaque verdict sont lus — les Empans de preuve n'existent pas encore à ce
    stade, ils naissent avec l'Entretien.
    """

    fiche_visee: Fiche
    phenomenes: list[PhenomeneAdverse] = []
    """Les difficultés que l'Entretien devra réaliser, chacune rattachée à sa cible."""
    style: Style = Style()
    """Les axes de style, en variables contrôlées — c'est par eux qu'on ventile les chiffres."""


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

Quand la commande porte un champ positif, c'est un item filtre : l'entretien doit établir
sa réponse dans ce sens-là, et tu le rapportes dans le champ positif du verdict.

Pour chaque propriété vraie, cite les tours qui l'établissent par leur indice : role
"sollicitation" pour un tour du clinicien, "renseignement" pour un tour du patient. Pour
chaque empan, recopie le passage exact — un extrait littéral du tour cité, pas une
reformulation, et le fragment utile plutôt que le tour entier.

Difficultés à réaliser dans cet entretien :
{phenomenes}

Style de l'entretien, à respecter :
- loquacité du patient : {loquacite}
- coopération du patient : {cooperation}
- directivité du clinicien : {directivite}

Items :
{items}
"""


def _rendre_commande(specification: Specification, registre: RegistreDItems) -> str:
    vises = specification.fiche_visee.par_identifiant()
    filtres = registre.items_filtres()
    lignes = []
    for ident in registre.identifiants():
        vise = vises[ident]
        ligne = f"- {ident} : sollicite={vise.sollicite}, renseigne={vise.renseigne}"
        if ident in filtres and vise.positif is not None:
            ligne += f", positif={vise.positif}"
        lignes.append(ligne)
    return "\n".join(lignes)


def _rendre_phenomenes(specification: Specification) -> str:
    if not specification.phenomenes:
        return "- aucune : entretien sans difficulté imposée"
    return "\n".join(
        f"- {phenomene.nature.value} sur {phenomene.cible}"
        for phenomene in specification.phenomenes
    )


def _rendre_items(registre: RegistreDItems) -> str:
    return "\n".join(
        f"{module} :\n{decrire_module(registre, module)}" for module in registre.modules()
    )


def _verifier_phenomenes(specification: Specification, registre: RegistreDItems) -> None:
    """Un Phénomène doit viser quelque chose, et ne pas contredire la commande.

    Les natures qui impliquent un état ne sont pas des nuances de génération : déclarer
    une question sans réponse sur un Item commandé renseigné serait une Spécification qui
    se contredit, et l'Entretien produit ne pourrait satisfaire les deux.
    """
    vises = specification.fiche_visee.par_identifiant()
    polarites = specification.fiche_visee.polarites()

    for phenomene in specification.phenomenes:
        if phenomene.nature is NaturePhenomene.MODULE_SAUTE:
            porte = registre.portes_de_module.get(phenomene.cible)
            if porte is None:
                raise GenerationInfidele(
                    f"{phenomene.nature.value} vise « {phenomene.cible} », "
                    "qui n'est pas un Module porteur d'une porte"
                )
            if porte.evaluer(polarites) is not False:
                raise GenerationInfidele(
                    f"{phenomene.nature.value} sur le Module {phenomene.cible} : la porte "
                    "du Module n'est pas établie négative par les polarités commandées — "
                    "un Module n'est pas sauté par décret, il l'est parce que son filtre "
                    "est négatif"
                )
            continue

        vise = vises.get(phenomene.cible)
        if vise is None:
            raise GenerationInfidele(
                f"{phenomene.nature.value} vise « {phenomene.cible} », "
                "qui n'est pas une entrée de la Spécification"
            )
        sollicite, renseigne = _ETATS_IMPLIQUES[phenomene.nature]
        if (sollicite is not None and vise.sollicite is not sollicite) or (
            renseigne is not None and vise.renseigne is not renseigne
        ):
            raise GenerationInfidele(
                f"{phenomene.nature.value} sur {phenomene.cible} : la nature impose "
                f"sollicite={sollicite}, renseigne={renseigne}, mais la commande dit "
                f"sollicite={vise.sollicite}, renseigne={vise.renseigne}"
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

    tours = {tour.indice: tour for tour in produit.retranscription.tours}
    vises = specification.fiche_visee.par_identifiant()
    rendus = produit.reference.par_identifiant()
    filtres = registre.items_filtres()
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

        if identifiant in filtres and obtenu.positif is not attendu.positif:
            raise GenerationInfidele(
                f"{identifiant} : polarité commandée à {attendu.positif}, "
                f"obtenu {obtenu.positif} — la référence doit porter ce qui a été commandé, "
                "sans quoi le graphe déroulé sur elle dit autre chose que la commande"
            )

        for empan in obtenu.empans:
            tour = tours.get(empan.indice_tour)
            if tour is None:
                raise GenerationInfidele(
                    f"{identifiant} : empan sur le tour {empan.indice_tour}, qui n'existe pas"
                )
            if tour.locuteur is not empan.role.locuteur:
                raise GenerationInfidele(
                    f"{identifiant} : empan de {empan.role.value} sur le tour "
                    f"{empan.indice_tour}, qui est un tour du {tour.locuteur.value}"
                )
            if empan.passage not in tour.texte:
                raise GenerationInfidele(
                    f"{identifiant} : le passage cité au tour {empan.indice_tour} "
                    f"ne figure pas dans ce tour"
                )

        if identifiant not in filtres:
            # ADR-0006 : la portée de l'exception vaut aussi à cette frontière-ci.
            obtenu = obtenu.model_copy(update={"positif": None})
        reference.append(obtenu)

    return Fiche(verdicts=reference)


def generer(
    specification: Specification, registre: RegistreDItems, modele: PortModele
) -> Entretien:
    """Dérive un Entretien de la Spécification, et refuse celui qui ne la réalise pas."""
    _verifier_couverture(specification, registre)
    _verifier_phenomenes(specification, registre)
    prompt = _CONSIGNE.format(
        commande=_rendre_commande(specification, registre),
        phenomenes=_rendre_phenomenes(specification),
        loquacite=specification.style.loquacite.value,
        cooperation=specification.style.cooperation.value,
        directivite=specification.style.directivite.value,
        items=_rendre_items(registre),
    )
    produit = modele.repondre(prompt, Entretien)
    return Entretien(
        retranscription=produit.retranscription,
        reference=_verifier(produit, specification, registre),
    )
