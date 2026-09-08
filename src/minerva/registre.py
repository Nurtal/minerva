"""Le Registre d'items : ce contre quoi MINERVA mesure. Aucun appel de modèle.

Le Registre est reconstruit depuis la littérature publiée et ne contient aucun libellé
d'Item du MINI — voir ADR-0002 et ADR-0003. Chaque entrée cite la source publiée dont
son construct est tiré, ce qui rend la reconstruction auditable sans être refaite.

MINERVA mesure donc la couverture d'un Registre reconstruit aligné sur la structure du
MINI, et non la couverture du MINI.
"""

from collections.abc import Mapping
from collections.abc import Set as AbstractSet

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class Lecture(BaseModel):
    """Une lecture d'une source publiée : la citation, et le construct qu'on y a lu.

    Conserver `construct_lu` à côté de la citation, plutôt que la seule citation, est ce
    qui rend l'écart vérifiable : sans les deux lectures, « les sources divergent » serait
    une affirmation qu'aucun relecteur ne pourrait contrôler sans refaire le travail.

    Nommée « lecture » et non « provenance » : dans MINERVA une provenance est le modèle
    générateur d'un Entretien (ADR-0004), et réemployer le mot ici ferait croire à un lien
    entre deux notions qui n'en ont aucun.
    """

    model_config = ConfigDict(frozen=True)

    source: str
    construct_lu: str


class EntreeDuRegistre(BaseModel):
    """Ce que toute entrée du Registre porte, quelle que soit sa nature.

    Les provenances sont exigées ici et nulle part ailleurs : c'est ADR-0003 appliqué en
    un seul endroit plutôt que redit à chaque type.
    """

    identifiant: str
    module: str
    construct_sonde: str
    """Le construct retenu, exprimé dans nos termes — jamais un libellé du MINI (ADR-0002)."""
    lectures: tuple[Lecture, ...]
    """Les lectures dont ce construct est tiré, deux au moins et de sources distinctes.

    ADR-0003 veut la reconstruction menée deux fois : une lecture unique ne serait pas une
    reconstruction contrôlée mais une affirmation, et rien ne distinguerait un construct
    solide d'un construct disputé.
    """
    ecart: str | None = None
    """Ce sur quoi les deux lectures divergent, et rien d'autre.

    `None` veut dire « les sources concordent », pas « on n'a pas regardé » — le
    validateur de double lecture garantit qu'on a regardé. C'est ce champ qui cartographie
    les Items sur lesquels ne pas tirer de conclusions.

    Strictement la divergence : une réserve qui ne vient pas d'un désaccord entre les
    sources va dans `reserve`. Les mélanger rendrait `est_disputee` vrai là où les
    nosographies s'accordent, et la carte des Items incertains cesserait d'en être une.
    """
    reserve: str | None = None
    """Une réserve sur cette entrée qui ne soit pas un désaccord entre les sources.

    Un héritage de classification, un chevauchement entre Modules de l'instrument : des
    choses qu'il faut savoir en lisant les chiffres, mais qui ne disent rien de la
    fidélité de la reconstruction.
    """

    @model_validator(mode="after")
    def _reconstruction_menee_deux_fois(self) -> "EntreeDuRegistre":
        if len(self.lectures) < 2:
            raise ValueError(
                f"{self.identifiant} : une entrée cite au moins deux lectures. Une seule "
                "n'est pas une reconstruction contrôlée, c'est une affirmation (ADR-0003)"
            )
        sources = [provenance.source for provenance in self.lectures]
        if len(set(sources)) < len(sources):
            raise ValueError(
                f"{self.identifiant} : les lectures doivent venir de sources distinctes. "
                "Relire deux fois le même texte mesure la constance du lecteur, pas le "
                "désaccord des nosographies (ADR-0003)"
            )
        return self

    def sources(self) -> tuple[str, ...]:
        """Les sources citées, dans l'ordre où elles ont été lues."""
        return tuple(provenance.source for provenance in self.lectures)

    def est_disputee(self) -> bool:
        """Les deux lectures divergent-elles sur cette entrée ?

        Interrogeable, et pas seulement lisible : c'est ce qui permettra de ventiler les
        chiffres selon qu'un Item est sûr ou disputé, plutôt que de le découvrir en
        relisant la prose des sources. Une `reserve` ne rend pas une entrée disputée.
        """
        return self.ecart is not None


class Item(EntreeDuRegistre):
    """Une entrée qui correspond à une question numérotée du MINI."""

    porte: Porte | None = None
    """Porte du second étage : ce qui doit être vrai pour que cet Item soit attendu."""


class Qualificatif(EntreeDuRegistre):
    """Une entrée du Registre de portée Module, dont les Items du Module héritent.

    Cadre temporel, fréquence : ce que le MINI présente en tête de module et que le
    Clinicien relit aussi souvent que nécessaire. Ne correspond à aucune question du MINI,
    et c'est assumé — le Registre est notre objet, pas l'instrument.

    Se sollicite et se renseigne comme un Item, ce qui rend visible l'Entretien qui
    n'établit jamais l'ancienneté des troubles.
    """


class RegistreDItems(BaseModel):
    """Les entrées connues de MINERVA — Items et Qualificatifs — groupées par Module."""

    items: list[Item]
    qualificatifs: list[Qualificatif] = []
    portes_de_module: dict[str, Porte] = {}
    """Portes du premier étage : le filtre en tête de chaque Module qui en a un."""

    @model_validator(mode="after")
    def _un_seul_qualificatif_par_module(self) -> "RegistreDItems":
        modules = [qualificatif.module for qualificatif in self.qualificatifs]
        doublons = sorted({module for module in modules if modules.count(module) > 1})
        if doublons:
            raise ValueError(
                f"plusieurs Qualificatifs pour le ou les Modules {', '.join(doublons)} : "
                "seul le premier serait présenté au modèle, les autres seraient exigés de "
                "la Spécification sans jamais être collectés"
            )
        return self

    def modules(self) -> list[str]:
        modules = [item.module for item in self.items]
        modules += [qualificatif.module for qualificatif in self.qualificatifs]
        vus: list[str] = []
        for module in modules:
            if module not in vus:
                vus.append(module)
        return vus

    def items_du_module(self, module: str) -> list[Item]:
        return [item for item in self.items if item.module == module]

    def entrees(self) -> list[EntreeDuRegistre]:
        """Toutes les entrées du Registre — Items et Qualificatifs — dans l'ordre.

        C'est la forme que suit une Fiche : un Qualificatif y porte son verdict au même
        titre qu'un Item. Rendre les entrées et non leurs seuls identifiants évite à
        l'appelant qui a besoin du construct de rechercher chaque entrée à la main, ce
        qui redonnerait ici un parcours déjà écrit trois fois.
        """
        return [*self.items, *self.qualificatifs]

    def identifiants(self) -> list[str]:
        """Les identifiants de toutes les entrées, dans le même ordre."""
        return [entree.identifiant for entree in self.entrees()]

    def qualificatif_du_module(self, module: str) -> Qualificatif | None:
        return next((q for q in self.qualificatifs if q.module == module), None)

    def a_une_porte(self, module: str) -> bool:
        return module in self.portes_de_module

    def module_ferme(self, module: str, polarites: Mapping[str, Polarite]) -> bool:
        """Le filtre du Module est-il établi négatif ? Indéterminé vaut non fermé."""
        porte = self.portes_de_module.get(module)
        return porte is not None and porte.evaluer(polarites) is False

    def cotables(self, renseignes: AbstractSet[str], non_applicables: AbstractSet[str]) -> set[str]:
        """Les Items cotables : contenu renseigné **et** cadre de leur Module établi.

        Le MINI cote sur une durée et une fréquence, pas sur un symptôme nu. Un Module
        sans Qualificatif n'impose aucun cadre, et ses Items sont cotables dès qu'ils sont
        renseignés.

        L'exigence de cadre tombe quand le Qualificatif est lui-même Non-applicable : le
        Module a été écarté à raison, il n'y a rien à dater.

        Ne rend que des Items : un Qualificatif est une condition de cotation, pas une
        chose qu'on cote.
        """
        cadres = {
            qualificatif.module: qualificatif.identifiant in renseignes
            or qualificatif.identifiant in non_applicables
            for qualificatif in self.qualificatifs
        }
        return {
            item.identifiant
            for item in self.items
            if item.identifiant in renseignes and cadres.get(item.module, True)
        }

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
        entrees: list[tuple[str, str, Porte | None]] = [
            (item.identifiant, item.module, item.porte) for item in self.items
        ]
        # Un Qualificatif suit le sort de son Module : un Module écarté n'a pas
        # d'ancienneté à dater, et lui réclamer son cadre serait un reproche absurde.
        entrees += [(q.identifiant, q.module, None) for q in self.qualificatifs]

        return {
            identifiant
            for identifiant, module, porte in entrees
            if (module in modules_fermes and identifiant not in modules_fermes[module])
            or (porte is not None and porte.evaluer(polarites) is False)
        }

    def entrees_du_module(self, module: str) -> list[str]:
        """Les identifiants attendus dans une Fiche pour ce Module, Qualificatif compris."""
        identifiants = [item.identifiant for item in self.items_du_module(module)]
        qualificatif = self.qualificatif_du_module(module)
        return identifiants + ([qualificatif.identifiant] if qualificatif else [])


DSM = (
    "APA, DSM-5-TR (2022), critères A1-A9 de l'épisode dépressif caractérisé : cinq "
    "symptômes ou plus sur deux semaines, dont au moins l'humeur dépressive ou la perte "
    "d'intérêt."
)
CIM = (
    "OMS, CIM-11 (6A70), épisode dépressif. Structure lue chez Parker G., « A critique of "
    "ICD-11 criteria for the mood disorders », Aust N Z J Psychiatry 59(8), 2025, "
    "674-678 : dix critères CDDR en trois grappes — deux affectives, quatre "
    "cognitivo-comportementales, quatre neurovégétatives — dont cinq requis, au moins un "
    "de la grappe affective. Énumération des symptômes lue chez Shevlin M. et al., "
    "« The development and initial validation of self-report measures of ICD-11 "
    "depressive episode… (IDQ) », J Clin Psychol 79(3), 2023, 854-870."
)


def _cadre_du_module_a() -> Qualificatif:
    return Qualificatif(
        identifiant="A_cadre",
        module="A",
        construct_sonde=(
            "Depuis quand cela dure et à quelle fréquence : au moins deux semaines, la "
            "plus grande partie du temps, presque chaque jour."
        ),
        lectures=(
            Lecture(
                source=DSM,
                construct_lu=(
                    "Critère A : symptômes présents sur une même période de deux semaines, "
                    "la majeure partie de la journée, presque tous les jours."
                ),
            ),
            Lecture(
                source=CIM,
                construct_lu=(
                    "Cinq symptômes présents conjointement la majeure partie de la "
                    "journée, presque tous les jours, sur deux semaines."
                ),
            ),
        ),
    )


def _porte_du_module_a() -> Porte:
    return Porte(
        au_moins=1,
        parmi=["A1", "A2"],
        source=(
            f"{DSM} L'épisode requiert l'humeur dépressive ou la perte d'intérêt. "
            f"Recoupé par : {CIM} La grappe affective porte exactement ces deux symptômes, "
            "et au moins un des cinq requis doit en venir — les deux nosographies "
            "s'accordent sur la porte, par des chemins différents."
        ),
    )


def registre_module_a() -> RegistreDItems:
    """Le Module A : épisode dépressif caractérisé, neuf critères symptomatiques.

    Chaque construct est lu deux fois — DSM-5-TR et CIM-11 — et l'écart conservé quand les
    nosographies divergent (ADR-0003). Les constructs sont reformulés dans nos termes, et
    délibérément plus proches de la langue d'un entretien que de celle d'un manuel : ni le
    MINI (ADR-0002) ni la traduction française du DSM-5-TR ne sont recopiés ici.

    La numérotation est une hypothèse déclarée, pas une lecture de l'instrument — voir
    ADR-0007, qui dit ce qui est supposé et ce qu'une licence viendrait corriger.
    """
    porte_du_module = _porte_du_module_a()
    return RegistreDItems(
        qualificatifs=[_cadre_du_module_a()],
        portes_de_module={"A": porte_du_module},
        items=[
            Item(
                identifiant="A1",
                module="A",
                construct_sonde=(
                    "Le patient se sent triste ou abattu, sans répit ou presque, depuis au "
                    "moins deux semaines."
                ),
                lectures=(
                    Lecture(source=DSM, construct_lu="Critère A1 : humeur dépressive."),
                    Lecture(
                        source=CIM,
                        construct_lu="Grappe affective, premier symptôme : humeur dépressive.",
                    ),
                ),
            ),
            Item(
                identifiant="A2",
                module="A",
                construct_sonde=(
                    "Ce qui procurait du plaisir n'en procure plus, sur presque tout ce que "
                    "le patient faisait."
                ),
                lectures=(
                    Lecture(
                        source=DSM,
                        construct_lu="Critère A2 : diminution marquée de l'intérêt ou du plaisir.",
                    ),
                    Lecture(
                        source=CIM,
                        construct_lu=(
                            "Grappe affective, second symptôme : diminution de l'intérêt ou "
                            "du plaisir."
                        ),
                    ),
                ),
            ),
            Item(
                identifiant="A3a",
                module="A",
                construct_sonde=(
                    "Le sommeil est perturbé : le patient dort beaucoup moins, ou beaucoup "
                    "plus, qu'à son ordinaire."
                ),
                lectures=(
                    Lecture(
                        source=DSM,
                        construct_lu=(
                            "Critère A4 : insomnie ou hypersomnie, symptôme distinct du "
                            "critère A3 qui porte l'appétit et le poids."
                        ),
                    ),
                    Lecture(
                        source=CIM,
                        construct_lu=(
                            "Grappe neurovégétative. La liste MMS réunit « modification de "
                            "l'appétit ou du sommeil » en un seul symptôme ; les CDDR les "
                            "séparent, d'où dix critères là où la MMS en compte neuf."
                        ),
                    ),
                ),
                ecart=(
                    "Le sommeil n'a pas le même grain selon la source. Le DSM-5-TR en fait "
                    "un critère à part entière, distinct de l'appétit ; la CIM-11 le réunit "
                    "à l'appétit dans sa liste MMS et ne l'en sépare que dans les CDDR. Un "
                    "entretien qui n'explore que le sommeil renseigne pleinement le critère "
                    "DSM et à moitié le symptôme MMS. À ne pas lire comme un item sûr."
                ),
            ),
            Item(
                identifiant="A3b",
                module="A",
                construct_sonde=(
                    "L'appétit a changé, ou le poids a bougé sans que le patient l'ait "
                    "cherché."
                ),
                lectures=(
                    Lecture(
                        source=DSM,
                        construct_lu=(
                            "Critère A3 : perte ou gain de poids significatif, ou "
                            "modification de l'appétit presque tous les jours."
                        ),
                    ),
                    Lecture(
                        source=CIM,
                        construct_lu=(
                            "Grappe neurovégétative, réuni au sommeil dans la liste MMS et "
                            "séparé dans les CDDR."
                        ),
                    ),
                ),
                ecart=(
                    "Même écart de grain que A3a, vu de l'autre côté : ce que le DSM-5-TR "
                    "sépare en deux critères, la liste MMS de la CIM-11 réunit en un. Les "
                    "deux items sont solidaires de cette divergence."
                ),
            ),
            Item(
                identifiant="A3c",
                module="A",
                construct_sonde=(
                    "Le patient bouge ou parle plus lentement qu'avant, ou au contraire ne "
                    "tient pas en place — au point que l'entourage le remarque."
                ),
                lectures=(
                    Lecture(
                        source=DSM,
                        construct_lu="Critère A5 : agitation ou ralentissement psychomoteur.",
                    ),
                    Lecture(
                        source=CIM,
                        construct_lu=(
                            "Grappe neurovégétative : agitation ou ralentissement psychomoteur."
                        ),
                    ),
                ),
            ),
            Item(
                identifiant="A3d",
                module="A",
                construct_sonde="Le patient se sent vidé, sans énergie, presque chaque jour.",
                lectures=(
                    Lecture(source=DSM, construct_lu="Critère A6 : fatigue ou perte d'énergie."),
                    Lecture(
                        source=CIM,
                        construct_lu=(
                            "Grappe neurovégétative : énergie réduite ou épuisement. La "
                            "CIM-10 en faisait un symptôme principal ; la CIM-11 l'a "
                            "reclassé parmi les symptômes additionnels."
                        ),
                    ),
                ),
                reserve=(
                    "Les deux sources retenues s'accordent, donc aucun écart. Mais la "
                    "fatigue a changé de rang entre les révisions de la CIM : symptôme "
                    "principal en CIM-10, additionnel en CIM-11. Un entretien conduit sous "
                    "l'ancienne classification la traiterait comme une question d'entrée."
                ),
            ),
            Item(
                identifiant="A3e",
                module="A",
                construct_sonde=(
                    "Le patient se juge sans valeur, ou s'accuse de choses hors de proportion."
                ),
                lectures=(
                    Lecture(
                        source=DSM,
                        construct_lu=(
                            "Critère A7 : sentiment de dévalorisation ou culpabilité "
                            "excessive ou inappropriée. Le désespoir ne figure pas parmi "
                            "les neuf critères."
                        ),
                    ),
                    Lecture(
                        source=CIM,
                        construct_lu=(
                            "Grappe cognitivo-comportementale : faible estime de soi. "
                            "L'énumération de Shevlin et al. y porte le désespoir comme "
                            "symptôme distinct — Parker, qui ne donne que la structure en "
                            "grappes, ne l'énumère pas."
                        ),
                    ),
                ),
                ecart=(
                    "La CIM-11 porte le désespoir comme symptôme à part entière, distinct "
                    "de la faible estime de soi ; le DSM-5-TR ne le retient pas comme "
                    "critère. La numérotation de ce Registre étant calée sur le DSM, le "
                    "désespoir n'a aucune case ici : un entretien qui l'explore ne "
                    "renseigne rien de mesurable. C'est le trou de couverture le plus net "
                    "de la reconstruction, et il est structurel, pas accidentel."
                ),
            ),
            Item(
                identifiant="A3f",
                module="A",
                construct_sonde=(
                    "Penser, se concentrer ou trancher une décision est devenu difficile."
                ),
                lectures=(
                    Lecture(
                        source=DSM,
                        construct_lu=(
                            "Critère A8 : diminution de l'aptitude à penser ou à se "
                            "concentrer, ou indécision."
                        ),
                    ),
                    Lecture(
                        source=CIM,
                        construct_lu=(
                            "Grappe cognitivo-comportementale : difficultés de concentration."
                        ),
                    ),
                ),
            ),
            Item(
                identifiant="A3g",
                module="A",
                construct_sonde=(
                    "La mort revient dans les pensées du patient : envie d'en finir, projet "
                    "arrêté, ou geste déjà posé."
                ),
                lectures=(
                    Lecture(
                        source=DSM,
                        construct_lu=(
                            "Critère A9 : pensées de mort récurrentes, idées suicidaires "
                            "sans plan précis, tentative, ou plan précis."
                        ),
                    ),
                    Lecture(
                        source=CIM,
                        construct_lu=(
                            "Grappe cognitivo-comportementale : pensées de mort récurrentes "
                            "ou actes suicidaires."
                        ),
                    ),
                ),
                reserve=(
                    "Les deux sources s'accordent, donc aucun écart. Mais le Module B porte "
                    "le risque suicidaire pour lui-même : un entretien qui explore le "
                    "suicide renseignera une entrée de chaque Module, et les Empans de "
                    "preuve se recouvriront. Chevauchement de l'instrument, à trancher "
                    "quand le Module B entrera au Registre."
                ),
            ),
        ],
    )


def registre_module_a_reduit() -> RegistreDItems:
    """Trois Items du Module A, le strict nécessaire au tracer bullet.

    Dérivé du Registre complet plutôt que recopié : deux listes tenues à la main auraient
    divergé, et chacune se présente comme la reconstruction sourcée du même construct. La
    divergence se serait lue comme un désaccord entre nosographies alors qu'elle n'aurait
    été qu'une faute de recopie.
    """
    gardes = ("A1", "A2", "A3a")
    complet = registre_module_a()
    return RegistreDItems(
        items=[item for item in complet.items if item.identifiant in gardes],
        qualificatifs=complet.qualificatifs,
        portes_de_module=complet.portes_de_module,
    )
