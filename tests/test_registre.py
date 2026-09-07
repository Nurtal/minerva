"""Le graphe de saut : portes du Registre et dérivation du Non-applicable.

Fonctions pures — ni modèle, ni Retranscription. C'est ce qui les rend exhaustivement
testables, et c'est la raison pour laquelle le graphe vit dans `registre`.
"""

import itertools

from minerva.registre import Condition, Item, RegistreDItems

GATE_IMBRIQUEE = Condition(
    au_moins=1,
    parmi=[
        Condition(au_moins=3, parmi=["G1a", "G1b", "G2"]),
        Condition(au_moins=2, parmi=["G3a", "G3b"]),
    ],
)
"""La forme réelle d'une porte du MINI : (G1a ET G1b ET G2) OU (G3a ET G3b)."""


def _oracle(condition: Condition, polarites: dict[str, bool | None]) -> bool | None:
    """Vérité de référence, calculée autrement que l'implémentation.

    Une porte vaut vrai si toutes les complétions des inconnues la rendent vraie, faux si
    toutes la rendent fausse, et indéterminée sinon. C'est la définition de la logique à
    trois valeurs prise à la lettre, par énumération — là où l'implémentation compte.
    """
    inconnues = [ident for ident, valeur in polarites.items() if valeur is None]
    resultats = set()
    for completion in itertools.product([True, False], repeat=len(inconnues)):
        connues = {ident: valeur for ident, valeur in polarites.items() if valeur is not None}
        complet = connues | dict(zip(inconnues, completion, strict=True))
        resultats.add(_evaluer_totalement(condition, complet))
    return resultats.pop() if len(resultats) == 1 else None


def _evaluer_totalement(condition: Condition, polarites: dict[str, bool]) -> bool:
    vrais = sum(
        1
        for operande in condition.parmi
        if (
            polarites[operande]
            if isinstance(operande, str)
            else _evaluer_totalement(operande, polarites)
        )
    )
    return vrais >= condition.au_moins


def test_les_portes_sont_evaluees_exhaustivement_en_logique_a_trois_valeurs() -> None:
    """Les 3^5 états possibles d'une porte imbriquée réelle, comparés à un oracle indépendant."""
    identifiants = ["G1a", "G1b", "G2", "G3a", "G3b"]
    etats: list[bool | None] = [True, False, None]

    cas = 0
    for combinaison in itertools.product(etats, repeat=len(identifiants)):
        polarites = dict(zip(identifiants, combinaison, strict=True))
        assert GATE_IMBRIQUEE.evaluer(polarites) == _oracle(GATE_IMBRIQUEE, polarites), polarites
        cas += 1

    assert cas == 3**5


def test_une_porte_dont_une_polarite_manque_reste_indeterminee_et_non_fausse() -> None:
    """C'est le point qui empêche la métrique de récompenser un entretien qui ne demande rien.

    Un filtre jamais établi ne rend pas ses items Non-applicables : le clinicien avait le
    devoir de l'établir. Seule une porte établie *et* négative excuse ce qui suit.
    """
    porte = Condition(au_moins=1, parmi=["A1", "A2"])

    assert porte.evaluer({"A1": None, "A2": None}) is None
    assert porte.evaluer({"A1": False, "A2": None}) is None
    assert porte.evaluer({"A1": False, "A2": False}) is False
    assert porte.evaluer({"A1": True, "A2": None}) is True


def registre_avec_portes() -> RegistreDItems:
    """Un Module A à deux étages : filtre d'entrée A1/A2, puis une porte interne sur A3a."""
    return RegistreDItems(
        items=[
            Item(identifiant="A1", module="A", construct_sonde="humeur", source="test"),
            Item(identifiant="A2", module="A", construct_sonde="anhédonie", source="test"),
            Item(identifiant="A3a", module="A", construct_sonde="sommeil", source="test"),
            Item(
                identifiant="A3b",
                module="A",
                construct_sonde="détail du sommeil",
                source="test",
                porte=Condition(au_moins=1, parmi=["A3a"]),
            ),
        ],
        portes_de_module={"A": Condition(au_moins=1, parmi=["A1", "A2"])},
    )


def test_un_filtre_d_entree_negatif_rend_le_reste_du_module_non_applicable() -> None:
    """Le premier étage : le Module est écarté, mais jamais ses propres filtres.

    Un clinicien qui établit que ni l'humeur ni l'anhédonie ne sont là a le droit de
    passer au Module suivant. Ce n'est pas un oubli.
    """
    non_applicables = registre_avec_portes().non_applicables({"A1": False, "A2": False})

    assert non_applicables == {"A3a", "A3b"}


def test_un_filtre_jamais_etabli_ne_rend_rien_non_applicable() -> None:
    """Le garde-fou : ne rien demander n'excuse rien.

    Sans cette règle, un entretien vide verrait tous ses Items devenir Non-applicables et
    obtiendrait un score parfait sur un dénominateur réduit à néant.
    """
    non_applicables = registre_avec_portes().non_applicables({"A1": None, "A2": None})

    assert non_applicables == set()


def test_une_porte_interne_negative_n_ecarte_que_ce_qu_elle_garde() -> None:
    """Le second étage : le Module reste ouvert, seul l'Item gardé tombe."""
    non_applicables = registre_avec_portes().non_applicables(
        {"A1": True, "A2": None, "A3a": False}
    )

    assert non_applicables == {"A3b"}


def test_les_items_filtres_sont_ceux_dont_le_graphe_a_besoin() -> None:
    """La polarité n'est stockée que là où le graphe l'exige — ADR-0006, et nulle part ailleurs."""
    assert registre_avec_portes().items_filtres() == {"A1", "A2", "A3a"}
