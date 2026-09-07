"""Le Non-applicable, évalué deux fois, et croisé avec le Sollicité observé.

Dérouler le graphe sur les polarités prédites puis sur celles de référence isole l'erreur
de propagation de l'erreur de détection : un seul Item filtre manqué peut faire tomber un
Module entier, et il faut que ce soit mesuré plutôt que supposé.
"""

from minerva.domaine import EmpanDePreuve, Fiche, RoleEmpan, VerdictItem
from minerva.evaluation import evaluer
from minerva.registre import Porte, RegistreDItems
from tests.fabriques import item


def registre() -> RegistreDItems:
    return RegistreDItems(
        items=[
            item("A1"),
            item("A2"),
            item("A3a"),
        ],
        portes_de_module={"A": Porte(au_moins=1, parmi=["A1", "A2"])},
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

    assert mesures.propagation.ecartes_a_tort == {"A3a": 1}
    assert mesures.propagation.accord == 2 / 3


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

    assert mesures.conduite.questions_inutiles == {"A3a": 1}
    assert mesures.conduite.oublis == {"A2": 1}


def test_un_item_tantot_inutile_tantot_oublie_ne_se_confond_pas_sur_un_corpus() -> None:
    """Le croisement doit distinguer, pas confondre — et un corpus n'est pas un entretien.

    Le même Item peut être une question inutile dans un Entretien et un oubli dans un
    autre. Une union d'identifiants le ferait apparaître dans les deux listes sans dire
    combien de fois : la distinction que le croisement existe pour produire disparaîtrait
    au moment même où le corpus grandit.
    """
    inutile = Fiche(
        verdicts=[
            verdict("A1", sollicite=True, renseigne=True, positif=False),
            verdict("A2", sollicite=True, renseigne=True, positif=False),
            verdict("A3a", sollicite=True),
        ]
    )
    oublie = Fiche(
        verdicts=[
            verdict("A1", sollicite=True, renseigne=True, positif=True),
            verdict("A2", sollicite=True, renseigne=True, positif=False),
            verdict("A3a"),
        ]
    )

    mesures = evaluer([(inutile, inutile), (oublie, oublie)], registre())

    assert mesures.conduite.questions_inutiles == {"A3a": 1}
    assert mesures.conduite.oublis == {"A3a": 1}


def test_un_item_apporte_spontanement_par_le_patient_n_est_pas_un_oubli() -> None:
    """Renseigné sans avoir été sollicité, l'entretien a obtenu le contenu.

    Le compter comme un oubli véritable reprocherait au clinicien de ne pas avoir posé
    une question dont il a eu la réponse.
    """
    fiche = Fiche(
        verdicts=[
            verdict("A1", sollicite=True, renseigne=True, positif=True),
            verdict("A2", sollicite=True, renseigne=True, positif=False),
            verdict("A3a", sollicite=False, renseigne=True),
        ]
    )

    mesures = evaluer([(fiche, fiche)], registre())

    assert "A3a" not in mesures.conduite.oublis


def test_l_ampleur_d_un_effondrement_se_compte_et_ne_se_nomme_pas_seulement() -> None:
    """Un effondrement sur un entretien et un effondrement sur dix ne sont pas le même défaut."""
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

    une_fois = evaluer([(reference, prediction)], registre())
    trois_fois = evaluer([(reference, prediction)] * 3, registre())

    assert une_fois.propagation.ecartes_a_tort == {"A3a": 1}
    assert trois_fois.propagation.ecartes_a_tort == {"A3a": 3}
