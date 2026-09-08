"""Le Registre du Module A, reconstruit depuis le DSM-5-TR et la CIM-11.

La numérotation du MINI n'a pas pu être vérifiée : l'instrument est sous licence et les
seules copies intégrales en ligne sont des republications non autorisées, que l'ADR-0002
désigne nommément. La décomposition en identifiants est donc une **hypothèse déclarée**,
et ces tests la fixent pour qu'une licence obtenue plus tard la corrige par diff.

Ce qui n'est pas hypothétique : les constructs eux-mêmes, lus deux fois dans deux
nosographies publiées, et les écarts entre elles.
"""

from minerva.registre import registre_module_a

SYMPTOMES_ADDITIONNELS = ("A3a", "A3b", "A3c", "A3d", "A3e", "A3f", "A3g")


def test_le_module_porte_les_neuf_criteres_symptomatiques() -> None:
    """Deux symptômes d'entrée et sept symptômes additionnels : le squelette du DSM-5-TR.

    C'est la part que les deux nosographies définissent explicitement, donc la seule que
    la reconstruction puisse porter sans inventer.
    """
    registre = registre_module_a()

    assert [item.identifiant for item in registre.items] == [
        "A1",
        "A2",
        *SYMPTOMES_ADDITIONNELS,
    ]
    assert registre.qualificatif_du_module("A") is not None


def test_chaque_entree_est_lue_dans_les_deux_nosographies() -> None:
    """ADR-0003 sur le contenu livré, pas seulement sur le type."""
    for entree in registre_module_a().entrees():
        sources = entree.sources()

        assert len(sources) >= 2, entree.identifiant
        assert len(set(sources)) == len(sources), entree.identifiant


def test_la_porte_du_module_est_le_couple_humeur_interet() -> None:
    """Les deux nosographies s'accordent sur la porte, par des chemins différents.

    Le DSM-5-TR exige l'humeur dépressive ou la perte d'intérêt ; la CIM-11 exige au moins
    un symptôme de sa grappe affective, qui porte exactement ces deux-là.
    """
    porte = registre_module_a().portes_de_module["A"]

    assert porte.au_moins == 1
    assert set(porte.identifiants()) == {"A1", "A2"}


def test_les_symptomes_additionnels_sont_ecartes_quand_la_porte_est_negative() -> None:
    """Un module correctement sauté n'est pas une série d'oublis."""
    registre = registre_module_a()

    non_applicables = registre.non_applicables({"A1": False, "A2": False})

    assert set(SYMPTOMES_ADDITIONNELS) <= non_applicables
    # Les filtres eux-mêmes restent attendus : ce sont les questions d'entrée.
    assert "A1" not in non_applicables
    assert "A2" not in non_applicables


PHQ9 = {
    1: ("A2", "peu d'intérêt ou de plaisir à faire les choses"),
    2: ("A1", "se sentir triste, déprimé ou désespéré"),
    3: ("A3a", "difficultés d'endormissement, réveils, ou trop dormir"),
    4: ("A3d", "fatigue ou manque d'énergie"),
    5: ("A3b", "manque d'appétit ou trop manger"),
    6: ("A3e", "mauvaise estime de soi, sentiment d'échec"),
    7: ("A3f", "difficultés de concentration"),
    8: ("A3c", "lenteur ou agitation remarquée par autrui"),
    9: ("A3g", "pensées qu'il vaudrait mieux être mort, ou de se faire du mal"),
}
"""Les neuf items du PHQ-9, chacun en regard de l'entrée du Registre qui le couvre.

Kroenke, Spitzer & Williams, J Gen Intern Med 16(9), 2001, 606-613. Instrument libre,
utilisé ici comme contrôle de couverture et non comme substitut au MINI (ADR-0003).
"""


def test_le_phq9_ne_trouve_aucun_construct_majeur_absent() -> None:
    """Le contrôle croisé qu'exige le ticket, exécutable plutôt qu'affirmé.

    Le PHQ-9 est bâti sur les neuf critères du DSM, un item par critère. Si un construct
    majeur manquait au Registre, un item du PHQ-9 se retrouverait sans correspondance —
    c'est tout l'intérêt de croiser avec un instrument libre dont la couverture est connue.
    """
    connues = {entree.identifiant for entree in registre_module_a().entrees()}

    non_couverts = {
        rang: construct for rang, (ident, construct) in PHQ9.items() if ident not in connues
    }

    assert not non_couverts, f"constructs du PHQ-9 sans entrée au Registre : {non_couverts}"
    assert len({ident for ident, _ in PHQ9.values()}) == 9, (
        "chaque item du PHQ-9 doit tomber sur une entrée distincte ; deux items sur la même "
        "entrée signalerait un construct du Registre trop large"
    )


def test_le_desespoir_echappe_au_controle_croise_et_c_est_documente() -> None:
    """Le PHQ-9 range le désespoir avec l'humeur dépressive ; la CIM-11 l'en sépare.

    Le contrôle croisé ne peut donc pas voir ce trou : son item 2 tombe sur A1 et repart
    satisfait. C'est la limite de la méthode, et la raison pour laquelle l'écart doit être
    conservé au Registre plutôt que déduit d'une couverture apparemment complète.
    """
    entrees = {entree.identifiant: entree for entree in registre_module_a().entrees()}

    assert "désespoir" in (entrees["A3e"].ecart or ""), (
        "le trou de couverture sur le désespoir doit être écrit au Registre : aucun "
        "contrôle croisé par le PHQ-9 ne le révélera"
    )
    assert entrees["A3e"].est_disputee()
