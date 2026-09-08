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


class Provenance(BaseModel):
    """Une lecture : la source publiée, et le construct qu'on y a lu.

    Conserver `construct_lu` à côté de la citation, plutôt que la seule citation, est ce
    qui rend l'écart vérifiable : sans les deux lectures, « les sources divergent » serait
    une affirmation qu'aucun relecteur ne pourrait contrôler sans refaire le travail.
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
    provenances: tuple[Provenance, ...]
    """Les lectures dont ce construct est tiré, deux au moins et de sources distinctes.

    ADR-0003 veut la reconstruction menée deux fois : une lecture unique ne serait pas une
    reconstruction contrôlée mais une affirmation, et rien ne distinguerait un construct
    solide d'un construct disputé.
    """
    ecart: str | None = None
    """Ce sur quoi les lectures divergent, quand elles divergent.

    `None` veut dire « les sources concordent », pas « on n'a pas regardé » — le
    validateur de double provenance garantit qu'on a regardé. C'est ce champ qui
    cartographie les Items sur lesquels ne pas tirer de conclusions.
    """

    @model_validator(mode="after")
    def _reconstruction_menee_deux_fois(self) -> "EntreeDuRegistre":
        if len(self.provenances) < 2:
            raise ValueError(
                f"{self.identifiant} : une entrée cite au moins deux lectures. Une seule "
                "n'est pas une reconstruction contrôlée, c'est une affirmation (ADR-0003)"
            )
        sources = [provenance.source for provenance in self.provenances]
        if len(set(sources)) < len(sources):
            raise ValueError(
                f"{self.identifiant} : les lectures doivent venir de sources distinctes. "
                "Relire deux fois le même texte mesure la constance du lecteur, pas le "
                "désaccord des nosographies (ADR-0003)"
            )
        return self

    def sources(self) -> tuple[str, ...]:
        """Les sources citées, dans l'ordre où elles ont été lues."""
        return tuple(provenance.source for provenance in self.provenances)

    def est_disputee(self) -> bool:
        """Les lectures divergent-elles sur cette entrée ?

        Interrogeable, et pas seulement lisible : c'est ce qui permettra de ventiler les
        chiffres selon qu'un Item est sûr ou disputé, plutôt que de le découvrir en
        relisant la prose des sources.
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
PHQ9 = (
    "Kroenke K., Spitzer R. L. & Williams J. B. W., « The PHQ-9: validity of a brief "
    "depression severity measure », J Gen Intern Med 16(9), 2001, 606-613."
)


def registre_module_a_reduit() -> RegistreDItems:
    """Trois Items du Module A, le strict nécessaire au tracer bullet.

    Le Module A complet — ses six Items et leurs quinze questions cotées — relève d'un
    ticket dédié, qui attend la numérotation de l'instrument.

    Chaque entrée est lue deux fois, dans le DSM-5-TR et dans la CIM-11, et l'écart est
    conservé quand il y en a un (ADR-0003). Les constructs sont exprimés dans nos termes :
    aucun libellé du MINI ne figure ici (ADR-0002).
    """
    return RegistreDItems(
        qualificatifs=[
            Qualificatif(
                identifiant="A_cadre",
                module="A",
                construct_sonde=(
                    "Ancienneté et permanence des troubles : présents depuis au moins deux "
                    "semaines, la majeure partie du temps, presque tous les jours."
                ),
                provenances=(
                    Provenance(
                        source=DSM,
                        construct_lu=(
                            "Critère A : les symptômes sont présents sur une même période "
                            "de deux semaines, la majeure partie de la journée, presque "
                            "tous les jours."
                        ),
                    ),
                    Provenance(
                        source=CIM,
                        construct_lu=(
                            "Cinq symptômes présents conjointement la majeure partie de la "
                            "journée, presque tous les jours, sur deux semaines."
                        ),
                    ),
                ),
            )
        ],
        portes_de_module={
            # Le filtre en tête du Module A : humeur dépressive OU perte d'intérêt.
            # Établi négatif sur les deux, le reste du Module est légitimement écarté.
            "A": Porte(
                au_moins=1,
                parmi=["A1", "A2"],
                source=(
                    f"{DSM} L'épisode requiert l'humeur dépressive ou la perte d'intérêt. "
                    f"Recoupé par : {CIM} La grappe affective porte exactement ces deux "
                    "symptômes, et au moins un des cinq requis doit en venir — les deux "
                    "nosographies s'accordent sur la porte, par des chemins différents."
                ),
            ),
        },
        items=[
            Item(
                identifiant="A1",
                module="A",
                construct_sonde=(
                    "Humeur dépressive présente la majeure partie de la journée, presque "
                    "tous les jours, depuis au moins deux semaines."
                ),
                provenances=(
                    Provenance(source=DSM, construct_lu="Critère A1 : humeur dépressive."),
                    Provenance(
                        source=CIM,
                        construct_lu=(
                            "Premier des deux symptômes de la grappe affective : humeur dépressive."
                        ),
                    ),
                ),
            ),
            Item(
                identifiant="A2",
                module="A",
                construct_sonde=(
                    "Diminution marquée de l'intérêt ou du plaisir pour toutes ou presque "
                    "toutes les activités, sur la même période."
                ),
                provenances=(
                    Provenance(
                        source=DSM,
                        construct_lu=(
                            "Critère A2 : diminution marquée de l'intérêt ou du plaisir."
                        ),
                    ),
                    Provenance(
                        source=CIM,
                        construct_lu=(
                            "Second des deux symptômes de la grappe affective : diminution "
                            "de l'intérêt ou du plaisir."
                        ),
                    ),
                ),
            ),
            Item(
                identifiant="A3a",
                module="A",
                construct_sonde=(
                    "Insomnie ou hypersomnie presque tous les jours sur la même période."
                ),
                provenances=(
                    Provenance(
                        source=DSM,
                        construct_lu=(
                            "Critère A4 : insomnie ou hypersomnie, symptôme distinct du "
                            "critère A3 qui porte l'appétit et le poids."
                        ),
                    ),
                    Provenance(
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
                    "entretien qui n'explore que le sommeil renseigne donc pleinement le "
                    "critère DSM, et à moitié seulement le symptôme MMS. À ne pas lire "
                    "comme un item sûr."
                ),
            ),
        ],
    )


_HYPOTHESE_DE_NUMEROTATION = """\
La numérotation du MINI n'a pas pu être vérifiée. L'instrument est sous licence, et les
seules copies intégrales accessibles en ligne sont des republications non autorisées —
celles-là mêmes que l'ADR-0002 cite comme illégales. La décomposition ci-dessous est donc
une hypothèse, déclarée comme telle :

- `A1` et `A2` portent les deux symptômes d'entrée, et `A3a` à `A3g` les sept symptômes
  additionnels. Ce découpage prolonge celui que le dépôt utilisait déjà pour le tracer
  bullet ; il n'est pas lu dans l'instrument.
- `A3a` reste le sommeil, comme dans le Registre réduit, alors que le DSM-5-TR place
  l'appétit avant lui. Conserver l'affectation existante évite une renumérotation qui
  invaliderait les Corpus déjà produits, mais elle est arbitraire.
- L'issue #5 annonce six Items et quinze questions cotées. Cette reconstruction porte les
  neuf critères symptomatiques, soit les seuls que le DSM-5-TR et la CIM-11 définissent
  explicitement. Le retentissement fonctionnel, la récurrence et les spécificateurs, que
  l'instrument numérote aussi, ne sont pas reconstruits : aucune des deux sources ne dit
  comment le MINI les numérote, et les inventer donnerait un Registre faussement complet.

Le jour où une licence est obtenue, la vérification est un diff sur ces identifiants —
c'est précisément la conséquence qu'ADR-0003 cherchait à préserver.
"""


def registre_module_a() -> RegistreDItems:
    """Le Module A : épisode dépressif caractérisé, neuf critères symptomatiques.

    Chaque construct est lu deux fois — DSM-5-TR et CIM-11 — et l'écart conservé quand les
    nosographies divergent (ADR-0003). Les constructs sont exprimés dans nos termes :
    aucun libellé du MINI ne figure ici (ADR-0002).

    Sur la numérotation, qui est une hypothèse et non une lecture : voir
    `_HYPOTHESE_DE_NUMEROTATION` juste au-dessus. Le résumé tient en une phrase — le MINI
    est sous licence, sa numérotation n'a pas pu être vérifiée, et ce découpage prolonge
    celui du Registre réduit sans être lu dans l'instrument.
    """
    return RegistreDItems(
        qualificatifs=[
            Qualificatif(
                identifiant="A_cadre",
                module="A",
                construct_sonde=(
                    "Ancienneté et permanence des troubles : présents depuis au moins deux "
                    "semaines, la majeure partie du temps, presque tous les jours."
                ),
                provenances=(
                    Provenance(
                        source=DSM,
                        construct_lu=(
                            "Critère A : symptômes présents sur une même période de deux "
                            "semaines, la majeure partie de la journée, presque tous les jours."
                        ),
                    ),
                    Provenance(
                        source=CIM,
                        construct_lu=(
                            "Cinq symptômes présents conjointement la majeure partie de la "
                            "journée, presque tous les jours, sur deux semaines."
                        ),
                    ),
                ),
            )
        ],
        portes_de_module={
            "A": Porte(
                au_moins=1,
                parmi=["A1", "A2"],
                source=(
                    f"{DSM} L'épisode requiert l'humeur dépressive ou la perte d'intérêt. "
                    f"Recoupé par : {CIM} La grappe affective porte exactement ces deux "
                    "symptômes, et au moins un des cinq requis doit en venir — les deux "
                    "nosographies s'accordent sur la porte, par des chemins différents."
                ),
            )
        },
        items=[
            Item(
                identifiant="A1",
                module="A",
                construct_sonde=(
                    "Humeur dépressive présente la majeure partie de la journée, presque "
                    "tous les jours, depuis au moins deux semaines."
                ),
                provenances=(
                    Provenance(source=DSM, construct_lu="Critère A1 : humeur dépressive."),
                    Provenance(
                        source=CIM,
                        construct_lu="Grappe affective, premier symptôme : humeur dépressive.",
                    ),
                ),
            ),
            Item(
                identifiant="A2",
                module="A",
                construct_sonde=(
                    "Diminution marquée de l'intérêt ou du plaisir pour toutes ou presque "
                    "toutes les activités, sur la même période."
                ),
                provenances=(
                    Provenance(
                        source=DSM,
                        construct_lu="Critère A2 : diminution marquée de l'intérêt ou du plaisir.",
                    ),
                    Provenance(
                        source=CIM,
                        construct_lu=(
                            "Grappe affective, second symptôme : diminution de l'intérêt "
                            "ou du plaisir."
                        ),
                    ),
                ),
            ),
            Item(
                identifiant="A3a",
                module="A",
                construct_sonde=(
                    "Insomnie ou hypersomnie presque tous les jours sur la même période."
                ),
                porte=Porte(au_moins=1, parmi=["A1", "A2"]),
                provenances=(
                    Provenance(
                        source=DSM,
                        construct_lu=(
                            "Critère A4 : insomnie ou hypersomnie, symptôme distinct du "
                            "critère A3 qui porte l'appétit et le poids."
                        ),
                    ),
                    Provenance(
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
                    "Modification de l'appétit ou variation de poids significative, non "
                    "intentionnelle, sur la même période."
                ),
                porte=Porte(au_moins=1, parmi=["A1", "A2"]),
                provenances=(
                    Provenance(
                        source=DSM,
                        construct_lu=(
                            "Critère A3 : perte ou gain de poids significatif, ou "
                            "modification de l'appétit presque tous les jours."
                        ),
                    ),
                    Provenance(
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
                    "Agitation ou ralentissement psychomoteur, observable par autrui et non "
                    "réduit à un sentiment subjectif."
                ),
                porte=Porte(au_moins=1, parmi=["A1", "A2"]),
                provenances=(
                    Provenance(
                        source=DSM,
                        construct_lu="Critère A5 : agitation ou ralentissement psychomoteur.",
                    ),
                    Provenance(
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
                construct_sonde="Fatigue ou perte d'énergie presque tous les jours.",
                porte=Porte(au_moins=1, parmi=["A1", "A2"]),
                provenances=(
                    Provenance(source=DSM, construct_lu="Critère A6 : fatigue ou perte d'énergie."),
                    Provenance(
                        source=CIM,
                        construct_lu=(
                            "Grappe neurovégétative : énergie réduite ou épuisement. La "
                            "CIM-10 en faisait un symptôme principal ; la CIM-11 l'a "
                            "reclassé parmi les symptômes additionnels."
                        ),
                    ),
                ),
                ecart=(
                    "La fatigue a changé de rang entre les révisions de la CIM : symptôme "
                    "principal en CIM-10, symptôme additionnel en CIM-11, alignée sur le "
                    "DSM. Les deux sources retenues s'accordent donc aujourd'hui, mais un "
                    "instrument construit sur la CIM-10 la traiterait comme une question "
                    "d'entrée. À surveiller si le Registre sert un jour à comparer des "
                    "entretiens conduits sous l'ancienne classification."
                ),
            ),
            Item(
                identifiant="A3e",
                module="A",
                construct_sonde=(
                    "Sentiment de dévalorisation, ou culpabilité excessive ou inappropriée."
                ),
                porte=Porte(au_moins=1, parmi=["A1", "A2"]),
                provenances=(
                    Provenance(
                        source=DSM,
                        construct_lu=(
                            "Critère A7 : sentiment de dévalorisation ou culpabilité "
                            "excessive ou inappropriée."
                        ),
                    ),
                    Provenance(
                        source=CIM,
                        construct_lu=(
                            "Grappe cognitivo-comportementale : faible estime de soi, "
                            "distincte du désespoir, qui y figure comme symptôme séparé."
                        ),
                    ),
                ),
                ecart=(
                    "La CIM-11 porte le désespoir comme symptôme à part entière de sa "
                    "grappe cognitivo-comportementale ; le DSM-5-TR ne le retient pas comme "
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
                    "Diminution de l'aptitude à penser ou à se concentrer, ou indécision."
                ),
                porte=Porte(au_moins=1, parmi=["A1", "A2"]),
                provenances=(
                    Provenance(
                        source=DSM,
                        construct_lu=(
                            "Critère A8 : diminution de l'aptitude à penser ou à se "
                            "concentrer, ou indécision."
                        ),
                    ),
                    Provenance(
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
                    "Pensées de mort récurrentes, idées suicidaires, ou geste ou plan suicidaire."
                ),
                porte=Porte(au_moins=1, parmi=["A1", "A2"]),
                provenances=(
                    Provenance(
                        source=DSM,
                        construct_lu=(
                            "Critère A9 : pensées de mort récurrentes, idées suicidaires "
                            "sans plan précis, tentative, ou plan précis."
                        ),
                    ),
                    Provenance(
                        source=CIM,
                        construct_lu=(
                            "Grappe cognitivo-comportementale : pensées de mort récurrentes "
                            "ou actes suicidaires."
                        ),
                    ),
                ),
                ecart=(
                    "Le Module B porte le risque suicidaire pour lui-même. Un entretien qui "
                    "explore le suicide renseigne donc potentiellement une entrée de chaque "
                    "module, et les empans de preuve se recouvriront. Ce n'est pas un "
                    "désaccord entre nosographies mais un chevauchement de l'instrument, à "
                    "trancher quand le Module B entrera au Registre."
                ),
            ),
        ],
    )
