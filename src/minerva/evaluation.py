"""Compare une Fiche de référence à une Fiche prédite. Fonction pure, aucun modèle.

L'évaluation est un diff entre deux objets de même type : c'est ce que garantit la
contrainte de forme, et c'est ce qui rend cette couche vérifiable sans réseau.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from minerva.domaine import Fiche, Propriete
from minerva.registre import RegistreDItems

PaireFiches = tuple[Fiche, Fiche]
"""Une Fiche de référence et la Fiche prédite pour le même Entretien."""


@dataclass(frozen=True)
class MesureBinaire:
    """Le résultat sur une propriété booléenne, macro-moyenné sur les Items.

    Un Item sans aucun positif — ni en référence, ni en prédiction — est écarté plutôt
    que compté comme un échec : il n'est pas mesurable sur ce corpus, et le compter
    zéro noierait le signal des Items réellement évalués.
    """

    precision: float
    rappel: float
    f1: float
    par_item: dict[str, float]
    """Le F1 de chaque Item mesurable, pour savoir lequel décroche sous la moyenne."""
    items_ecartes: tuple[str, ...]


@dataclass(frozen=True)
class MesureApplicabilite:
    """Ce que le graphe de saut dit, dérivé deux fois, et ce qu'il révèle de l'Entretien.

    Les deux premiers champs séparent l'erreur de propagation de l'erreur de détection ;
    les deux derniers ne parlent plus du détecteur mais du Clinicien.
    """

    accord: float
    """Part des Items où l'applicabilité dérivée des prédictions rejoint celle de référence."""
    ecartes_a_tort: tuple[str, ...]
    """Items que la prédiction écarte alors que la référence les attendait : l'effondrement."""
    retenus_a_tort: tuple[str, ...]
    """Items que la prédiction attend alors que la référence les écartait."""
    questions_inutiles: tuple[str, ...]
    """Items écartés par le graphe et pourtant sollicités par le Clinicien."""
    oublis: tuple[str, ...]
    """Items attendus par le graphe et que le Clinicien n'a pas sollicités."""


@dataclass(frozen=True)
class Mesures:
    """Les chiffres rendus pour un corpus.

    Le rappel sur `renseigne` est la métrique de tête : rater un Item que l'Entretien
    renseignait est l'erreur coûteuse, en signaler un de trop se corrige en relecture.
    """

    sollicite: MesureBinaire
    renseigne: MesureBinaire
    taux_ancrage: float
    applicabilite: MesureApplicabilite


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


def _applicabilite(
    paires: Sequence[PaireFiches], registre: RegistreDItems
) -> MesureApplicabilite:
    identifiants = registre.identifiants()
    accords = total = 0
    ecartes_a_tort: set[str] = set()
    retenus_a_tort: set[str] = set()
    inutiles: set[str] = set()
    oublis: set[str] = set()

    for reference, prediction in paires:
        selon_reference = registre.non_applicables(reference.polarites())
        selon_prediction = registre.non_applicables(prediction.polarites())
        verdicts_reference = reference.par_identifiant()

        for identifiant in identifiants:
            ecarte_reference = identifiant in selon_reference
            ecarte_prediction = identifiant in selon_prediction
            total += 1
            if ecarte_reference == ecarte_prediction:
                accords += 1
            elif ecarte_prediction:
                ecartes_a_tort.add(identifiant)
            else:
                retenus_a_tort.add(identifiant)

            # Le croisement décrit l'Entretien, pas le détecteur : il se lit sur la référence.
            verdict = verdicts_reference.get(identifiant)
            sollicite = bool(verdict and verdict.sollicite)
            if ecarte_reference and sollicite:
                inutiles.add(identifiant)
            elif not ecarte_reference and not sollicite:
                oublis.add(identifiant)

    return MesureApplicabilite(
        accord=accords / total if total else 0.0,
        ecartes_a_tort=tuple(sorted(ecartes_a_tort)),
        retenus_a_tort=tuple(sorted(retenus_a_tort)),
        questions_inutiles=tuple(sorted(inutiles)),
        oublis=tuple(sorted(oublis)),
    )


def evaluer(paires: Sequence[PaireFiches], registre: RegistreDItems) -> Mesures:
    """Rend les chiffres pour un corpus de Fiches appariées.

    Le F1 d'un Item se calcule sur l'ensemble des Entretiens du corpus, puis se moyenne
    sur les Items — un F1 par Item n'aurait aucun sens sur un seul Entretien, où chaque
    Item ne fournit qu'une observation.
    """
    return Mesures(
        sollicite=_mesurer(paires, Propriete.SOLLICITE),
        renseigne=_mesurer(paires, Propriete.RENSEIGNE),
        taux_ancrage=_ancrage(paires),
        applicabilite=_applicabilite(paires, registre),
    )
