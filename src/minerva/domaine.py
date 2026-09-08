"""Le vocabulaire du domaine, tel que défini dans CONTEXT.md.

Ces types sont partagés par les quatre modules. La Fiche est le type qui circule de
bout en bout : la Spécification en porte une, la détection en rend une, l'évaluation
en compare deux. C'est la contrainte de forme du projet.
"""

from collections.abc import Sequence
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

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


class IdentiteModele(BaseModel):
    """Qui a produit quelque chose : un modèle, et la famille dont il relève.

    La famille est plus grossière que le nom, délibérément. Un détecteur ne doit jamais
    être évalué sur ce qu'il a lui-même écrit ; mais son score contre un frère de sa
    propre famille reste intéressant, et son écart avec le score contre une autre famille
    est précisément ce qui mesure le biais de génération (ADR-0004).
    """

    model_config = ConfigDict(frozen=True)

    nom: str
    famille: str

    @field_validator("nom", "famille", mode="after")
    @classmethod
    def _normaliser(cls, valeur: str) -> str:
        """Casse et espaces ne doivent pas décider d'une contamination.

        Une valeur qui ne survit pas à la normalisation est refusée, et pas conservée
        vide : les deux gardes de la règle ne tiennent que par ces chaînes. Un nom vide
        est préfixe de tous les autres, donc `est_le_meme_que` vaut alors vrai contre
        n'importe qui ; une famille vide range dans une même partition des modèles
        étrangers l'un à l'autre.
        """
        normalisee = valeur.strip().casefold()
        if not normalisee:
            raise ValueError(
                "une identité de modèle ne peut être ni anonyme ni sans famille : la règle "
                "de non-contamination se lit entièrement sur ces deux chaînes"
            )
        return normalisee

    def est_le_meme_que(self, autre: "IdentiteModele") -> bool:
        """Deux identités désignent-elles le même modèle ?

        Un nom préfixe de l'autre suffit à le croire — « claude-opus-5 » et
        « claude-opus-5-20250101 » sont le même modèle épinglé différemment. La garde de
        contamination se trompe du côté sûr : deux modèles réellement distincts dont les
        noms se recouvrent doivent être désambiguïsés explicitement.
        """
        return self.nom.startswith(autre.nom) or autre.nom.startswith(self.nom)


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
    generateur: IdentiteModele | None = None
    """Le modèle qui a écrit cet Entretien, apposé à la génération.

    `None` pour un Entretien qui n'est pas sorti de `generer` — sa provenance est alors
    inconnue, et il n'a pas sa place dans un Corpus soumis à la règle de non-contamination.
    """


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
        par_generateur: dict[str, list[Entretien]] = {}
        for entretien in self.entretiens:
            if entretien.generateur is not None:
                par_generateur.setdefault(entretien.generateur.nom, []).append(entretien)
        return par_generateur

    def partition_neutre(self, panel: Sequence[IdentiteModele]) -> list[Entretien]:
        """Les Entretiens qu'aucun détecteur ni aucun de ses parents n'a écrits.

        La référence propre s'entend au niveau de la **famille**, pas du nom : un modèle
        absent du panel mais frère d'un détecteur partage ses régularités, et le prendre
        pour référence propre reviendrait à mesurer le biais avec le biais.

        Vide quand le Corpus n'a aucune partition étrangère au panel — mieux vaut le lire
        dans le résultat que le supposer.
        """
        familles = {identite.famille for identite in panel}
        return [
            entretien
            for entretien in self.entretiens
            if entretien.generateur is not None and entretien.generateur.famille not in familles
        ]
