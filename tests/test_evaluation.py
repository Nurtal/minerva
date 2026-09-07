"""L'évaluation compare une Fiche de référence à une Fiche prédite et rend des chiffres."""

from minerva.domaine import EmpanDePreuve, Fiche, RoleEmpan, VerdictItem
from minerva.evaluation import evaluer


def fiche(**etats: tuple[bool, bool]) -> Fiche:
    """Fiche concise pour les tests : identifiant=(sollicite, renseigne)."""
    return Fiche(
        verdicts=[
            VerdictItem(identifiant=ident, sollicite=sol, renseigne=ren, empans=[])
            for ident, (sol, ren) in etats.items()
        ]
    )


def test_f1_par_item_macro_moyenne_sur_le_corpus() -> None:
    """Le F1 d'un Item se calcule sur tous les Entretiens, puis se moyenne sur les Items.

    Exemple travaillé à la main sur deux Entretiens et trois Items.

    Sollicité — A1 : un vrai positif puis un faux négatif, donc précision 1, rappel 1/2, F1 2/3.
                A2 : un faux positif puis un vrai positif, donc précision 1/2, rappel 1, F1 2/3.
                A3 : aucun positif nulle part, écarté de la moyenne.
                Macro = 2/3.

    Renseigné — A1 et A2 sont parfaits, A3 est écarté. Macro = 1.
    """
    paires = [
        (
            fiche(A1=(True, True), A2=(False, False), A3=(False, False)),
            fiche(A1=(True, True), A2=(True, False), A3=(False, False)),
        ),
        (
            fiche(A1=(True, False), A2=(True, True), A3=(False, False)),
            fiche(A1=(False, False), A2=(True, True), A3=(False, False)),
        ),
    ]

    mesures = evaluer(paires)

    assert mesures.sollicite.f1 == 2 / 3
    assert mesures.renseigne.f1 == 1.0


def test_sollicite_et_renseigne_sont_mesures_separement() -> None:
    """Les deux propriétés sont indépendantes : une détection peut réussir l'une et rater l'autre.

    Sur un Item, la sollicitation est trouvée mais le renseignement est manqué.
    """
    paires = [(fiche(A1=(True, True)), fiche(A1=(True, False)))]

    mesures = evaluer(paires)

    assert mesures.sollicite.rappel == 1.0
    assert mesures.renseigne.rappel == 0.0


def test_item_sans_aucun_positif_est_ecarte_et_non_compte_zero() -> None:
    """Un Item jamais Sollicité ni prédit Sollicité n'est pas mesurable, pas raté.

    Le compter comme un F1 de zéro noierait le signal des Items réellement évalués.
    L'exclusion vaut propriété par propriété : un Item peut être mesurable sur
    Sollicité et écarté sur Renseigné.
    """
    paires = [
        (fiche(A1=(True, False), A3=(False, False)), fiche(A1=(True, False), A3=(False, False)))
    ]

    mesures = evaluer(paires)

    assert mesures.sollicite.items_ecartes == ("A3",)
    assert mesures.renseigne.items_ecartes == ("A1", "A3")


def verdict(
    identifiant: str,
    sollicite: bool,
    renseigne: bool,
    tours_sollicitation: tuple[int, ...] = (),
    tours_renseignement: tuple[int, ...] = (),
) -> VerdictItem:
    return VerdictItem(
        identifiant=identifiant,
        sollicite=sollicite,
        renseigne=renseigne,
        empans=[
            *(
                EmpanDePreuve(indice_tour=tour, role=RoleEmpan.SOLLICITATION, passage="question")
                for tour in tours_sollicitation
            ),
            *(
                EmpanDePreuve(indice_tour=tour, role=RoleEmpan.RENSEIGNEMENT, passage="réponse")
                for tour in tours_renseignement
            ),
        ],
    )


def test_taux_ancrage_compte_les_verdicts_justes_dont_l_empan_tombe_au_bon_endroit() -> None:
    """Un verdict juste dont l'Empan de preuve ne recouvre pas la référence est une intuition.

    Exemple travaillé — trois verdicts justes :
      A1 Sollicité, empan prédit au tour 0 comme en référence  -> ancré
      A1 Renseigné, empan prédit au tour 3 au lieu du tour 1   -> non ancré
      A2 Sollicité, empan prédit au tour 0 comme en référence  -> ancré
    Le tour 0 sollicite A1 et A2 à la fois : c'est une question groupée, et c'est
    exactement ce que la relation plusieurs-à-plusieurs doit permettre.
    Taux = 2/3.
    """
    reference = Fiche(
        verdicts=[
            verdict("A1", True, True, tours_sollicitation=(0,), tours_renseignement=(1,)),
            verdict("A2", True, False, tours_sollicitation=(0,)),
        ]
    )
    prediction = Fiche(
        verdicts=[
            verdict("A1", True, True, tours_sollicitation=(0,), tours_renseignement=(3,)),
            verdict("A2", True, False, tours_sollicitation=(0,)),
        ]
    )

    mesures = evaluer([(reference, prediction)])

    assert mesures.taux_ancrage == 2 / 3


def test_un_verdict_faux_positif_n_entre_pas_dans_l_ancrage() -> None:
    """Un Item que la référence ne porte pas n'a pas d'Empan de référence à recouvrir.

    Il est déjà puni par la précision ; le compter non ancré le punirait deux fois.
    """
    reference = Fiche(verdicts=[verdict("A1", True, False, tours_sollicitation=(0,))])
    prediction = Fiche(
        verdicts=[verdict("A1", True, True, tours_sollicitation=(0,), tours_renseignement=(2,))]
    )

    mesures = evaluer([(reference, prediction)])

    assert mesures.taux_ancrage == 1.0


def test_le_f1_de_chaque_item_reste_lisible_sous_la_moyenne() -> None:
    """La macro-moyenne existe pour que les Items rares ne se noient pas ; encore faut-il
    pouvoir dire lequel décroche. Un Item écarté n'apparaît pas — il n'a pas de F1."""
    paires = [
        (
            fiche(A1=(True, True), A2=(False, False), A3=(False, False)),
            fiche(A1=(True, True), A2=(True, False), A3=(False, False)),
        ),
        (
            fiche(A1=(True, False), A2=(True, True), A3=(False, False)),
            fiche(A1=(False, False), A2=(True, True), A3=(False, False)),
        ),
    ]

    mesures = evaluer(paires)

    assert mesures.sollicite.par_item == {"A1": 2 / 3, "A2": 2 / 3}
    assert mesures.renseigne.par_item == {"A1": 1.0, "A2": 1.0}
