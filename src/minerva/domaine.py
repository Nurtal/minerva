"""Le vocabulaire du domaine, tel que défini dans CONTEXT.md.

Ces types sont partagés par les quatre modules. La Fiche est le type qui circule de
bout en bout : la Spécification en porte une, la détection en rend une, l'évaluation
en compare deux. C'est la contrainte de forme du projet.
"""

from enum import StrEnum

from pydantic import BaseModel

Polarite = bool | None
"""Vrai, faux, ou indéterminé — la réponse à un Item filtre du graphe de saut."""


class Locuteur(StrEnum):
    """Qui parle dans un Tour de parole."""

    CLINICIEN = "clinicien"
    PATIENT = "patient"


class TourDeParole(BaseModel):
    """Une prise de parole continue d'un locuteur. Unité de base d'une Retranscription."""

    indice: int
    locuteur: Locuteur
    texte: str


class Retranscription(BaseModel):
    """Le texte intégral d'un Entretien, découpé en Tours de parole attribués."""

    tours: list[TourDeParole]


class RoleEmpan(StrEnum):
    """Ce qu'un Empan de preuve établit.

    Un empan de sollicitation est un Tour de parole du Clinicien, un empan de
    renseignement un Tour de parole du Patient. Ce ne sont pas les mêmes passages.
    """

    SOLLICITATION = "sollicitation"
    RENSEIGNEMENT = "renseignement"

    @property
    def locuteur(self) -> Locuteur:
        """Qui peut produire un Empan de ce rôle.

        Seul le Clinicien sollicite ; seul le Patient renseigne. C'est le glossaire.
        """
        return Locuteur.CLINICIEN if self is RoleEmpan.SOLLICITATION else Locuteur.PATIENT


class EmpanDePreuve(BaseModel):
    """Un passage de la Retranscription établissant qu'un Item est sollicité ou renseigné.

    Le passage est conservé tel quel, en plus de sa position : une Fiche seule doit
    pouvoir être lue sans la Retranscription. C'est de la dénormalisation assumée, et
    c'est ce qui donne à l'Empan une granularité plus fine que le Tour entier.

    Un Item porte plusieurs Empans et un même Tour peut servir plusieurs Items : la
    relation est plusieurs-à-plusieurs, ce qui permet de reconnaître une question groupée.
    """

    indice_tour: int
    role: RoleEmpan
    passage: str


class Propriete(StrEnum):
    """L'une des deux propriétés indépendantes d'un Item.

    Chaque propriété s'établit par un Empan de preuve d'un rôle précis : le Clinicien
    sollicite, le Patient renseigne. L'appariement est fixé ici, une fois.
    """

    SOLLICITE = "sollicite"
    RENSEIGNE = "renseigne"

    @property
    def role(self) -> RoleEmpan:
        return RoleEmpan.SOLLICITATION if self is Propriete.SOLLICITE else RoleEmpan.RENSEIGNEMENT


class VerdictItem(BaseModel):
    """Ce que MINERVA dit d'un Item pour un Entretien donné.

    Sollicité et Renseigné sont deux propriétés indépendantes : un Item peut être les
    deux, l'une sans l'autre dans les deux sens, ou aucune des deux.
    """

    identifiant: str
    sollicite: bool
    renseigne: bool
    empans: list[EmpanDePreuve]
    positif: Polarite = None
    """Polarité, pour les seuls Items filtres du graphe de saut — voir ADR-0006.

    `None` signifie indéterminée : soit l'Item n'est pas un filtre et MINERVA ne le code
    pas, soit c'est un filtre que l'Entretien n'a pas établi. Une polarité indéterminée
    n'écarte jamais rien.
    """

    @classmethod
    def negatif(cls, identifiant: str) -> "VerdictItem":
        """Le verdict d'un Item que rien dans l'Entretien n'a touché."""
        return cls(identifiant=identifiant, sollicite=False, renseigne=False, empans=[])

    def empans_de(self, role: RoleEmpan) -> list[EmpanDePreuve]:
        return [empan for empan in self.empans if empan.role == role]

    def porte(self, propriete: Propriete) -> bool:
        return self.sollicite if propriete is Propriete.SOLLICITE else self.renseigne

    def tours(self, role: RoleEmpan) -> set[int]:
        """Les Tours de parole cités comme preuve pour ce rôle."""
        return {empan.indice_tour for empan in self.empans_de(role)}


class Fiche(BaseModel):
    """L'ensemble des verdicts d'un Entretien, un par Item du Registre."""

    verdicts: list[VerdictItem]

    def par_identifiant(self) -> dict[str, VerdictItem]:
        return {verdict.identifiant: verdict for verdict in self.verdicts}

    def identifiants(self) -> set[str]:
        return {verdict.identifiant for verdict in self.verdicts}

    def polarites(self) -> dict[str, Polarite]:
        """Les polarités portées par cette Fiche, pour dérouler le graphe de saut."""
        return {verdict.identifiant: verdict.positif for verdict in self.verdicts}


class Loquacite(StrEnum):
    """Combien le Patient en dit."""

    LACONIQUE = "laconique"
    MOYENNE = "moyenne"
    PROLIXE = "prolixe"


class Cooperation(StrEnum):
    """Avec quelle disposition le Patient répond."""

    EVITANTE = "evitante"
    MOYENNE = "moyenne"
    COOPERANTE = "cooperante"


class Directivite(StrEnum):
    """Comment le Clinicien mène l'Entretien."""

    LIBRE = "libre"
    SEMI_DIRECTIF = "semi_directif"
    DIRECTIF = "directif"


class Style(BaseModel):
    """Les axes de style de l'Entretien, fixés par la Spécification.

    Variables contrôlées, jamais tirées au hasard : sans quoi une baisse de résultat
    resterait ininterprétable — on ne saurait pas si le modèle échoue sur les Patients
    évasifs ou sur les Entretiens longs. Les valeurs par défaut sont le milieu de chaque
    axe, et ce défaut est un choix explicite, pas une absence de choix.
    """

    loquacite: Loquacite = Loquacite.MOYENNE
    cooperation: Cooperation = Cooperation.MOYENNE
    directivite: Directivite = Directivite.SEMI_DIRECTIF


class AxeDeStyle(StrEnum):
    """Les axes selon lesquels on ventile les chiffres.

    Nommer les axes plutôt que lire des attributs par leur nom en chaîne : un champ de
    Style renommé devient alors une erreur de typage, pas une ventilation silencieusement
    vide.
    """

    LOQUACITE = "loquacite"
    COOPERATION = "cooperation"
    DIRECTIVITE = "directivite"

    def valeur(self, style: "Style") -> str:
        if self is AxeDeStyle.LOQUACITE:
            return style.loquacite.value
        if self is AxeDeStyle.COOPERATION:
            return style.cooperation.value
        return style.directivite.value


class Entretien(BaseModel):
    """Une Retranscription et la Fiche de référence qui la décrit, vraie par construction.

    Porte le Style sous lequel il a été produit : sans lui, ventiler les chiffres par axe
    obligerait à ré-apparier à la main une Spécification et une sortie de détection, ce
    qui est une erreur silencieuse et irrattrapable.
    """

    retranscription: Retranscription
    reference: Fiche
    style: Style = Style()
