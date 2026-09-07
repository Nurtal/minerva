"""Le Non-applicable, évalué deux fois, et croisé avec le Sollicité observé.

Dérouler le graphe sur les polarités prédites puis sur celles de référence isole l'erreur
de propagation de l'erreur de détection : un seul Item filtre manqué peut faire tomber un
Module entier, et il faut que ce soit mesuré plutôt que supposé.
"""

from minerva.domaine import EmpanDePreuve, Fiche, RoleEmpan, VerdictItem
from minerva.evaluation import evaluer
from minerva.registre import Condition, Item, RegistreDItems


def registre() -> RegistreDItems:
    return RegistreDItems(
        items=[
            Item(identifiant="A1", module="A", construct_sonde="humeur", source="test"),
            Item(identifiant="A2", module="A", construct_sonde="anhédonie", source="test"),
            Item(identifiant="A3a", module="A", construct_sonde="sommeil", source="test"),
        ],
        portes_de_module={"A": Condition(au_moins=1, parmi=["A1", "A2"])},
    )


def verdict(
    identifiant: str, sollicite: bool = False, renseigne: bool = False, positif: bool | None = None
) -> VerdictItem:
    empans = (
        [EmpanDePreuve(indice_tour=0, role=RoleEmpan.SOLLICITATION, passage="q")]
        if sollicite
        else []
    )
    return VerdictItem(
        identifiant=identifiant,
        sollicite=sollicite,
        renseigne=renseigne,
        positif=positif,
        empans=empans,
    )


def test_un_item_filtre_manque_fait_s_effondrer_le_module_et_ca_se_voit() -> None:
    """Le filtre était positif ; la détection le croit négatif, et tout le Module tombe.

    La référence n'écarte rien. La prédiction écarte A3a. L'écart nomme l'Item victime de
    la propagation, au lieu de le laisser se confondre avec une erreur de détection.
    """
    reference = Fiche(
        verdicts=[verdict("A1", renseigne=True, positif=True), verdict("A2"), verdict("A3a")]
    )
    prediction = Fiche(
        verdicts=[
            verdict("A1", renseigne=True, positif=False),
            verdict("A2", positif=False),
            verdict("A3a"),
        ]
    )

    mesures = evaluer([(reference, prediction)], registre())

    assert mesures.applicabilite.ecartes_a_tort == ("A3a",)
    assert mesures.applicabilite.accord == 2 / 3


def test_le_croisement_distingue_la_question_inutile_de_l_oubli() -> None:
    """Deux écarts de conduite que rien ne distingue sans le graphe de saut.

    Le filtre est établi négatif des deux côtés : A3a est légitimement écarté. Le clinicien
    l'a pourtant sollicité — question inutile. A2, lui, restait attendu et n'a pas été posé
    — oubli véritable.
    """
    fiche = Fiche(
        verdicts=[
            verdict("A1", sollicite=True, renseigne=True, positif=False),
            verdict("A2", positif=False),
            verdict("A3a", sollicite=True),
        ]
    )

    mesures = evaluer([(fiche, fiche)], registre())

    assert mesures.applicabilite.questions_inutiles == ("A3a",)
    assert mesures.applicabilite.oublis == ("A2",)
