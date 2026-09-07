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

from collections.abc import Set as AbstractSet
from enum import StrEnum

from pydantic import BaseModel, model_validator

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


class SpecificationIncoherente(ValueError):
    """La Spécification se contredit ou ne couvre pas le Registre — avant toute génération."""


class GenerationInfidele(RuntimeError):
    """L'Entretien produit ne réalise pas la Spécification qui l'a commandé."""


class NaturePhenomene(StrEnum):
    """Les difficultés qu'un Corpus doit éprouver, faute de quoi il n'éprouve rien.

    Ce que la Spécification peut vérifier varie selon la nature, et il faut le savoir en
    lisant les chiffres. SANS_REPONSE et APPORT_SPONTANE sont entièrement contraints par
    l'état visé, donc réalisés ou la génération échoue. NEGATION l'est aussi sur un Item
    filtre, par sa polarité — ailleurs, elle reste une consigne. FAUX_AMI n'est qu'une
    consigne : rien dans une Fiche ne distingue un faux ami résisté d'un Item jamais
    évoqué, et un modèle qui l'ignore passe sans qu'on le sache.
    """

    SANS_REPONSE = "sans_reponse"
    """Le Clinicien pose la question, le Patient n'apporte rien d'exploitable."""
    APPORT_SPONTANE = "apport_spontane"
    """Le Patient apporte le contenu sans qu'on le lui ait demandé."""
    FAUX_AMI = "faux_ami"
    """L'Entretien contient un contenu qui ressemble à l'Item sans en être."""
    NEGATION = "negation"
    """La réponse est explicitement négative — ce qui renseigne l'Item, et ne l'annule pas."""


_ETATS_IMPLIQUES: dict[NaturePhenomene, dict[Propriete, bool]] = {
    NaturePhenomene.SANS_REPONSE: {Propriete.SOLLICITE: True, Propriete.RENSEIGNE: False},
    NaturePhenomene.APPORT_SPONTANE: {Propriete.SOLLICITE: False, Propriete.RENSEIGNE: True},
    NaturePhenomene.NEGATION: {Propriete.RENSEIGNE: True},
    NaturePhenomene.FAUX_AMI: {},
}
"""Ce que chaque nature impose. La table est totale : toute nature y figure, donc une
nature nouvelle ne peut pas passer au travers sans qu'on ait décidé de son implication.

FAUX_AMI n'impose rien, délibérément : un contenu trompeur peut parfaitement coexister
avec l'Item réellement renseigné ailleurs dans l'Entretien, et c'est même le cas le plus
discriminant — le détecteur ancre-t-il son verdict sur le bon passage ? L'exiger non
renseigné supprimerait ce cas, et priverait l'Item de tout positif, ce qui l'écarterait
de la macro-moyenne (ADR-0005) au lieu de l'éprouver."""


class PhenomeneSurEntree(BaseModel):
    """Une difficulté visant une entrée précise du Registre."""

    nature: NaturePhenomene
    cible: str


class ModuleSaute(BaseModel):
    """Le filtre d'un Module est établi négatif et sa suite est écartée à raison.

    Type distinct plutôt que nature parmi les autres : ce Phénomène vise un Module et non
    une entrée, et un identifiant qui désignerait tantôt l'un tantôt l'autre serait une
    ambiguïté que rien ne rattraperait — pas même le prompt, qui la transmettrait telle
    quelle au modèle.
    """

    module: str


PhenomeneAdverse = PhenomeneSurEntree | ModuleSaute
"""Une difficulté que la Spécification impose de réaliser, rattachée à ce qu'elle vise."""


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


class CorpusSynthetique(BaseModel):
    """Les Entretiens générés, chacun sachant de quel modèle il vient.

    Le partitionnement n'est pas une vue posée sur le Corpus après coup : c'est sa
    structure. La règle de non-contamination ne se rattrape pas au moment de l'analyse,
    donc un Entretien de provenance inconnue n'y entre pas.
    """

    entretiens: list[Entretien]

    @model_validator(mode="after")
    def _provenance_connue(self) -> "CorpusSynthetique":
        orphelins = [
            indice
            for indice, entretien in enumerate(self.entretiens)
            if entretien.generateur is None
        ]
        if orphelins:
            raise ValueError(
                f"entretiens sans générateur aux positions {orphelins} : on ne pourrait "
                "pas dire s'ils contaminent un détecteur, et la règle reposerait sur la "
                "vigilance du lecteur"
            )
        return self

    def partitions(self) -> dict[str, list[Entretien]]:
        """Les Entretiens groupés par nom de générateur."""
        groupes: dict[str, list[Entretien]] = {}
        for entretien in self.entretiens:
            if entretien.generateur is not None:
                groupes.setdefault(entretien.generateur.nom, []).append(entretien)
        return groupes

    def generateurs(self) -> set[str]:
        return set(self.partitions())

    def partition_neutre(self, detecteurs: AbstractSet[str]) -> list[Entretien]:
        """Les Entretiens qu'aucun détecteur n'a écrits — la référence propre.

        Vide si chaque partition a été produite par un détecteur : le Corpus n'a alors
        aucune référence propre, et il vaut mieux le lire dans le résultat que le
        supposer.
        """
        return [
            entretien
            for entretien in self.entretiens
            if entretien.generateur is not None and entretien.generateur.nom not in detecteurs
        ]


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
        f"- module_saute sur le module {phenomene.module}"
        if isinstance(phenomene, ModuleSaute)
        else f"- {phenomene.nature.value} sur l'entrée {phenomene.cible}"
        for phenomene in specification.phenomenes
    )


def _rendre_items(registre: RegistreDItems) -> str:
    return "\n".join(
        f"{module} :\n{decrire_module(registre, module)}" for module in registre.modules()
    )


def _verifier_polarites(specification: Specification, registre: RegistreDItems) -> None:
    """Une polarité commandée exige un Item commandé renseigné.

    On ne peut pas avoir établi la réponse sans avoir l'information. Sans ce contrôle, une
    Spécification pourrait fermer un Module sur un filtre que l'Entretien n'établit jamais
    — et fabriquerait comme vérité terrain l'incitation même que l'ADR-0006 interdit.
    """
    filtres = registre.items_filtres()
    for vise in specification.fiche_visee.verdicts:
        if vise.positif is not None and not vise.renseigne:
            raise SpecificationIncoherente(
                f"{vise.identifiant} : polarité commandée à {vise.positif} sur une entrée "
                "commandée non renseignée — on n'établit pas une réponse qu'on n'a pas"
            )
        if vise.positif is not None and vise.identifiant not in filtres:
            raise SpecificationIncoherente(
                f"{vise.identifiant} : polarité commandée sur une entrée qui n'est pas un "
                "Item filtre — ADR-0006 n'excepte que ceux-là"
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
        if isinstance(phenomene, ModuleSaute):
            if not registre.a_une_porte(phenomene.module):
                raise SpecificationIncoherente(
                    f"module_saute vise « {phenomene.module} », "
                    "qui n'est pas un Module porteur d'une porte"
                )
            if not registre.module_ferme(phenomene.module, polarites):
                raise SpecificationIncoherente(
                    f"module_saute sur le Module {phenomene.module} : la porte du Module "
                    "n'est pas établie négative par les polarités commandées — un Module "
                    "n'est pas sauté par décret, il l'est parce que son filtre est négatif"
                )
            continue

        vise = vises.get(phenomene.cible)
        if vise is None:
            raise SpecificationIncoherente(
                f"{phenomene.nature.value} vise « {phenomene.cible} », "
                "qui n'est pas une entrée de la Spécification"
            )
        for propriete, impose in _ETATS_IMPLIQUES[phenomene.nature].items():
            if vise.porte(propriete) is not impose:
                raise SpecificationIncoherente(
                    f"{phenomene.nature.value} sur {phenomene.cible} : la nature impose "
                    f"{propriete.value}={impose}, mais la commande dit "
                    f"{propriete.value}={vise.porte(propriete)}"
                )
        if (
            phenomene.nature is NaturePhenomene.NEGATION
            and phenomene.cible in registre.items_filtres()
            and vise.positif is not False
        ):
            raise SpecificationIncoherente(
                f"negation sur le filtre {phenomene.cible} : une réponse explicitement "
                f"négative est une polarité négative, mais la commande dit "
                f"positif={vise.positif}"
            )


def _verifier_couverture(specification: Specification, registre: RegistreDItems) -> None:
    """Une Spécification doit viser chaque Item du Registre.

    Un Item absent n'est pas un Item non visé, c'est une commande trouée.
    """
    vises = specification.fiche_visee.identifiants()
    manquants = [ident for ident in registre.identifiants() if ident not in vises]
    if manquants:
        raise SpecificationIncoherente(
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
    _verifier_polarites(specification, registre)
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
        style=specification.style,
        generateur=modele.identite,
    )
