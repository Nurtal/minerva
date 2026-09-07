"""Compare une Fiche de référence à une Fiche prédite. Fonction pure, aucun modèle.

L'évaluation est un diff entre deux objets de même type : c'est ce que garantit la
contrainte de forme, et c'est ce qui rend cette couche vérifiable sans réseau.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from minerva.domaine import AxeDeStyle, Fiche, Propriete, Style
from minerva.registre import RegistreDItems

PaireFiches = tuple[Fiche, Fiche]
"""Une Fiche de référence et la Fiche prédite pour le même Entretien."""


@dataclass(frozen=True)
class MesureBinaire:
    """Le résultat sur une propriété booléenne, macro-moyenné sur les entrées du Registre.

    La moyenne porte sur **toutes** les entrées, Qualificatifs compris : détecter le cadre
    temporel d'un Module est une tâche de détection comme une autre, et l'écarter
    masquerait un échec réel. Un Qualificatif pèse donc autant qu'un Item.

    Une entrée sans aucun positif — ni en référence, ni en prédiction — est écartée plutôt
    que comptée comme un échec : elle n'est pas mesurable sur ce corpus, et la compter
    zéro noierait le signal des entrées réellement évaluées (ADR-0005).
    """

    precision: float
    rappel: float
    f1: float
    par_item: dict[str, float]
    """Le F1 de chaque entrée mesurable, pour savoir laquelle décroche sous la moyenne."""
    items_ecartes: tuple[str, ...]


@dataclass(frozen=True)
class MesurePropagation:
    """Ce que devient le graphe selon qu'on le déroule sur les prédictions ou la référence.

    Parle du détecteur : c'est ce qui isole l'erreur de propagation — un filtre mal détecté
    fait tomber tout un Module — de l'erreur de détection item par item.
    """

    accord: float
    """Part des Items où l'applicabilité dérivée des prédictions rejoint celle de référence."""
    ecartes_a_tort: dict[str, int]
    """Items que la prédiction écarte alors que la référence les attendait : l'effondrement.

    Compté par Entretien, pas seulement nommé : un effondrement sur un Entretien et un
    effondrement sur cent ne sont pas le même défaut.
    """
    retenus_a_tort: dict[str, int]
    """Items que la prédiction attend alors que la référence les écartait, par Entretien."""


@dataclass(frozen=True)
class ConduiteDEntretien:
    """Ce que le graphe révèle de l'Entretien lui-même, lu sur la référence.

    Ne parle pas du détecteur : ces listes décrivent la conduite du Clinicien, et
    resteraient vraies avec une détection parfaite.
    """

    questions_inutiles: dict[str, int]
    """Items écartés par le graphe et pourtant sollicités : la question qui ne servait à rien.

    Compté par Entretien. Un même Item peut être une question inutile ici et un oubli là ;
    une union d'identifiants effacerait la distinction au moment où le corpus grandit.
    """
    oublis: dict[str, int]
    """Items attendus, non sollicités, et dont l'Entretien n'a pas obtenu le contenu.

    Un Item que le Patient a renseigné de lui-même n'en est pas : reprocher la question
    non posée quand la réponse est là n'aurait pas de sens.
    """
    non_cotables_faute_de_cadre: dict[str, int]
    """Items dont le contenu est obtenu mais que le Qualificatif du Module ne rend pas cotables.

    Reproche distinct de l'oubli : les questions ont été posées, c'est l'ancienneté des
    troubles qui n'a jamais été établie — et sans elle le MINI ne cote rien.
    """


@dataclass(frozen=True)
class Mesures:
    """Les chiffres rendus pour un corpus.

    Le rappel sur `renseigne` est la métrique de tête : rater un Item que l'Entretien
    renseignait est l'erreur coûteuse, en signaler un de trop se corrige en relecture.
    """

    sollicite: MesureBinaire
    renseigne: MesureBinaire
    taux_ancrage: float
    propagation: MesurePropagation
    conduite: ConduiteDEntretien


@dataclass(frozen=True)
class _Comptes:
    vrais_positifs: int = 0
    faux_positifs: int = 0
    faux_negatifs: int = 0

    @property
    def sans_positif(self) -> bool:
        return not (self.vrais_positifs or self.faux_positifs or self.faux_negatifs)

    def plus(self, reference: bool, prediction: bool) -> "_Comptes":
        return _Comptes(
            vrais_positifs=self.vrais_positifs + (reference and prediction),
            faux_positifs=self.faux_positifs + (not reference and prediction),
            faux_negatifs=self.faux_negatifs + (reference and not prediction),
        )

    def precision(self) -> float:
        annonces = self.vrais_positifs + self.faux_positifs
        return self.vrais_positifs / annonces if annonces else 0.0

    def rappel(self) -> float:
        attendus = self.vrais_positifs + self.faux_negatifs
        return self.vrais_positifs / attendus if attendus else 0.0

    def f1(self) -> float:
        precision, rappel = self.precision(), self.rappel()
        somme = precision + rappel
        return 2 * precision * rappel / somme if somme else 0.0


def _moyenne(valeurs: list[float]) -> float:
    return sum(valeurs) / len(valeurs) if valeurs else 0.0


def _mesurer(paires: Sequence[PaireFiches], propriete: Propriete) -> MesureBinaire:
    identifiants = sorted(
        {
            ident
            for reference, prediction in paires
            for ident in reference.identifiants() | prediction.identifiants()
        }
    )

    comptes: dict[str, _Comptes] = {ident: _Comptes() for ident in identifiants}
    for reference, prediction in paires:
        verdicts_reference = reference.par_identifiant()
        verdicts_prediction = prediction.par_identifiant()
        for ident in identifiants:
            verdict_reference = verdicts_reference.get(ident)
            verdict_prediction = verdicts_prediction.get(ident)
            comptes[ident] = comptes[ident].plus(
                bool(verdict_reference and verdict_reference.porte(propriete)),
                bool(verdict_prediction and verdict_prediction.porte(propriete)),
            )

    mesurables = [ident for ident in identifiants if not comptes[ident].sans_positif]
    ecartes = tuple(ident for ident in identifiants if comptes[ident].sans_positif)

    par_item = {ident: comptes[ident].f1() for ident in mesurables}

    return MesureBinaire(
        precision=_moyenne([comptes[ident].precision() for ident in mesurables]),
        rappel=_moyenne([comptes[ident].rappel() for ident in mesurables]),
        f1=_moyenne(list(par_item.values())),
        par_item=par_item,
        items_ecartes=ecartes,
    )


def _ancrage(paires: Sequence[PaireFiches]) -> float:
    """Proportion des verdicts justes dont l'Empan de preuve recouvre celui de référence.

    Seuls les vrais positifs entrent au dénominateur : un faux positif n'a pas d'Empan de
    référence à recouvrir, et il est déjà puni par la précision.
    """
    ancres = total = 0
    for reference, prediction in paires:
        verdicts_prediction = prediction.par_identifiant()
        for identifiant, verdict_reference in reference.par_identifiant().items():
            verdict_prediction = verdicts_prediction.get(identifiant)
            if verdict_prediction is None:
                continue
            for propriete in Propriete:
                if not (verdict_reference.porte(propriete) and verdict_prediction.porte(propriete)):
                    continue
                total += 1
                role = propriete.role
                ancres += bool(verdict_reference.tours(role) & verdict_prediction.tours(role))
    return ancres / total if total else 0.0


@dataclass(frozen=True)
class EntretienEvalue:
    """Une Fiche de référence, la Fiche prédite, et le Style sous lequel l'Entretien fut produit.

    Le Style ne sert pas à mesurer : il sert à ventiler. Sans lui, une baisse de résultat
    ne dit pas si le modèle échoue sur les Patients évasifs ou sur les Entretiens longs.
    """

    style: Style
    reference: Fiche
    prediction: Fiche


def evaluer_par_axe(
    entretiens: Sequence[EntretienEvalue], registre: RegistreDItems
) -> dict[AxeDeStyle, dict[str, Mesures]]:
    """Les mêmes chiffres, ventilés axe par axe puis niveau par niveau.

    Un axe de style contrôlé ne sert à rien si les chiffres ne s'y rapportent pas : c'est
    la ventilation qui rend une baisse interprétable.

    Attention en comparant deux niveaux : chacun a son propre dénominateur, puisque les
    entrées sans aucun positif y sont écartées séparément (ADR-0005). Deux niveaux dont
    les `items_ecartes` diffèrent ne sont pas directement comparables.
    """
    par_axe: dict[AxeDeStyle, dict[str, Mesures]] = {}
    for axe in AxeDeStyle:
        groupes: dict[str, list[PaireFiches]] = {}
        for entretien in entretiens:
            niveau = axe.valeur(entretien.style)
            groupes.setdefault(niveau, []).append((entretien.reference, entretien.prediction))
        par_axe[axe] = {
            niveau: evaluer(paires, registre) for niveau, paires in sorted(groupes.items())
        }
    return par_axe


def _applicabilite(
    paires: Sequence[PaireFiches], registre: RegistreDItems
) -> tuple[MesurePropagation, ConduiteDEntretien]:
    identifiants = registre.identifiants()
    accords = total = 0
    ecartes_a_tort: Counter[str] = Counter()
    retenus_a_tort: Counter[str] = Counter()
    inutiles: Counter[str] = Counter()
    oublis: Counter[str] = Counter()
    sans_cadre: Counter[str] = Counter()

    for reference, prediction in paires:
        renseignes = {verdict.identifiant for verdict in reference.verdicts if verdict.renseigne}
        selon_reference = registre.non_applicables(reference.polarites())
        cotables = registre.cotables(renseignes, selon_reference)
        selon_prediction = registre.non_applicables(prediction.polarites())
        verdicts_reference = reference.par_identifiant()

        for identifiant in identifiants:
            ecarte_reference = identifiant in selon_reference
            ecarte_prediction = identifiant in selon_prediction
            total += 1
            if ecarte_reference == ecarte_prediction:
                accords += 1
            elif ecarte_prediction:
                ecartes_a_tort[identifiant] += 1
            else:
                retenus_a_tort[identifiant] += 1

            # Le croisement décrit l'Entretien, pas le détecteur : il se lit sur la référence.
            verdict = verdicts_reference.get(identifiant)
            sollicite = bool(verdict and verdict.sollicite)
            renseigne = bool(verdict and verdict.renseigne)
            if ecarte_reference and sollicite:
                inutiles[identifiant] += 1
            elif not ecarte_reference and not sollicite and not renseigne:
                oublis[identifiant] += 1
            if renseigne and identifiant in renseignes - cotables:
                sans_cadre[identifiant] += 1

    return (
        MesurePropagation(
            accord=accords / total if total else 0.0,
            ecartes_a_tort=dict(sorted(ecartes_a_tort.items())),
            retenus_a_tort=dict(sorted(retenus_a_tort.items())),
        ),
        ConduiteDEntretien(
            questions_inutiles=dict(sorted(inutiles.items())),
            oublis=dict(sorted(oublis.items())),
            non_cotables_faute_de_cadre=dict(sorted(sans_cadre.items())),
        ),
    )


def evaluer(paires: Sequence[PaireFiches], registre: RegistreDItems) -> Mesures:
    """Rend les chiffres pour un corpus de Fiches appariées.

    Le F1 d'un Item se calcule sur l'ensemble des Entretiens du corpus, puis se moyenne
    sur les Items — un F1 par Item n'aurait aucun sens sur un seul Entretien, où chaque
    Item ne fournit qu'une observation.
    """
    propagation, conduite = _applicabilite(paires, registre)
    return Mesures(
        sollicite=_mesurer(paires, Propriete.SOLLICITE),
        renseigne=_mesurer(paires, Propriete.RENSEIGNE),
        taux_ancrage=_ancrage(paires),
        propagation=propagation,
        conduite=conduite,
    )
