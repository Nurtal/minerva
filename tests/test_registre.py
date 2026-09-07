"""Le graphe de saut : portes du Registre et dérivation du Non-applicable.

Fonctions pures — ni modèle, ni Retranscription. C'est ce qui les rend exhaustivement
testables, et c'est la raison pour laquelle le graphe vit dans `registre`.
"""

import itertools

import pytest
from pydantic import ValidationError

from minerva.domaine import Polarite
from minerva.registre import Porte, RegistreDItems
from tests.fabriques import item

PORTE_IMBRIQUEE = Porte(
    au_moins=1,
    parmi=[
        Porte(au_moins=3, parmi=["G1a", "G1b", "G2"]),
        Porte(au_moins=2, parmi=["G3a", "G3b"]),
    ],
)
"""La forme réelle d'une porte du MINI : (G1a ET G1b ET G2) OU (G3a ET G3b)."""


def _oracle(condition: Porte, polarites: dict[str, bool | None]) -> bool | None:
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


def _evaluer_totalement(condition: Porte, polarites: dict[str, bool]) -> bool:
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
        assert PORTE_IMBRIQUEE.evaluer(polarites) == _oracle(PORTE_IMBRIQUEE, polarites), polarites
        cas += 1

    assert cas == 3**5


def test_une_porte_dont_une_polarite_manque_reste_indeterminee_et_non_fausse() -> None:
    """C'est le point qui empêche la métrique de récompenser un entretien qui ne demande rien.

    Un filtre jamais établi ne rend pas ses items Non-applicables : le clinicien avait le
    devoir de l'établir. Seule une porte établie *et* négative excuse ce qui suit.
    """
    porte = Porte(au_moins=1, parmi=["A1", "A2"])

    assert porte.evaluer({"A1": None, "A2": None}) is None
    assert porte.evaluer({"A1": False, "A2": None}) is None
    assert porte.evaluer({"A1": False, "A2": False}) is False
    assert porte.evaluer({"A1": True, "A2": None}) is True


def registre_avec_portes() -> RegistreDItems:
    """Un Module A à deux étages : filtre d'entrée A1/A2, puis une porte interne sur A3a."""
    return RegistreDItems(
        items=[
            item("A1"),
            item("A2"),
            item("A3a"),
            item("A3b", porte=Porte(au_moins=1, parmi=["A3a"])),
        ],
        portes_de_module={"A": Porte(au_moins=1, parmi=["A1", "A2"])},
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
    non_applicables = registre_avec_portes().non_applicables({"A1": True, "A2": None, "A3a": False})

    assert non_applicables == {"A3b"}


def test_les_items_filtres_sont_ceux_dont_le_graphe_a_besoin() -> None:
    """La polarité n'est stockée que là où le graphe l'exige — ADR-0006, et nulle part ailleurs."""
    assert registre_avec_portes().items_filtres() == {"A1", "A2", "A3a"}


def _non_applicables_par_enumeration(
    registre: RegistreDItems, polarites: dict[str, Polarite]
) -> set[str]:
    """Vérité de référence pour la dérivation, calculée autrement.

    Un Item est écarté si *toutes* les complétions des polarités inconnues l'écartent, la
    dérivation étant faite en logique à deux valeurs. L'implémentation, elle, propage
    l'indétermination à travers les portes.
    """
    inconnues = [ident for ident, valeur in polarites.items() if valeur is None]
    connues = {ident: valeur for ident, valeur in polarites.items() if valeur is not None}
    ecartes_partout: set[str] | None = None

    for completion in itertools.product([True, False], repeat=len(inconnues)):
        complet = connues | dict(zip(inconnues, completion, strict=True))
        ecartes = set()
        for entree in registre.items:
            porte_module = registre.portes_de_module.get(entree.module)
            ferme = (
                porte_module is not None
                and entree.identifiant not in porte_module.identifiants()
                and not _evaluer_totalement(porte_module, complet)
            )
            gardee = entree.porte is not None and not _evaluer_totalement(entree.porte, complet)
            if ferme or gardee:
                ecartes.add(entree.identifiant)
        ecartes_partout = ecartes if ecartes_partout is None else ecartes_partout & ecartes

    return ecartes_partout or set()


def test_la_derivation_est_exhaustive_sur_l_espace_d_entree_du_graphe() -> None:
    """Les 3^3 états des Items filtres du Registre, comparés à une énumération indépendante."""
    registre = registre_avec_portes()
    filtres = sorted(registre.items_filtres())
    etats: list[Polarite] = [True, False, None]

    cas = 0
    for combinaison in itertools.product(etats, repeat=len(filtres)):
        polarites = dict(zip(filtres, combinaison, strict=True))
        attendu = _non_applicables_par_enumeration(registre, polarites)
        assert registre.non_applicables(polarites) == attendu, polarites
        cas += 1

    assert cas == 3 ** len(filtres)


def test_une_porte_impossible_a_satisfaire_est_refusee() -> None:
    """Une porte qui exige plus d'opérandes qu'elle n'en a serait toujours fausse ;
    une qui n'en exige aucun serait toujours vraie. Ni l'une ni l'autre n'est une porte."""
    with pytest.raises(ValidationError):
        Porte(au_moins=3, parmi=["A1", "A2"])
    with pytest.raises(ValidationError):
        Porte(au_moins=0, parmi=["A1"])
