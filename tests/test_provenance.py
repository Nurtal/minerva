"""La double reconstruction, posée dans la structure du Registre.

ADR-0003 : « la reconstruction est menée deux fois depuis des sources distinctes et les
écarts sont conservés : ils cartographient les items incertains ». Une entrée qui ne
citerait qu'une lecture ne serait pas une reconstruction contrôlée, seulement une
affirmation — et rien ne distinguerait un construct solide d'un construct disputé.
"""

import pytest
from pydantic import ValidationError

from minerva.registre import EntreeDuRegistre, Item, Lecture, registre_module_a_reduit

DSM = "APA, DSM-5-TR (2022), critère A1 de l'épisode dépressif caractérisé."
CIM = "OMS, CIM-11 (6A70), grappe affective."


def lecture(source: str, lu: str = "humeur dépressive") -> Lecture:
    return Lecture(source=source, construct_lu=lu)


def test_une_entree_cite_au_moins_deux_lectures() -> None:
    """Une seule lecture n'est pas une reconstruction contrôlée, c'est une affirmation."""
    with pytest.raises(ValidationError, match="deux"):
        EntreeDuRegistre(
            identifiant="A1",
            module="A",
            construct_sonde="humeur dépressive",
            lectures=(lecture(DSM),),
        )


def test_deux_lectures_de_la_meme_source_ne_font_pas_une_double_reconstruction() -> None:
    """Relire deux fois le même texte ne cartographie aucune incertitude.

    C'est le point de l'ADR : les sources doivent être distinctes, sans quoi l'écart
    mesure la constance du lecteur et non le désaccord des nosographies.
    """
    with pytest.raises(ValidationError, match="distinctes"):
        EntreeDuRegistre(
            identifiant="A1",
            module="A",
            construct_sonde="humeur dépressive",
            lectures=(lecture(DSM), lecture(DSM, "humeur triste")),
        )


def test_une_entree_bien_sourcee_est_acceptee() -> None:
    item = Item(
        identifiant="A1",
        module="A",
        construct_sonde="humeur dépressive",
        lectures=(lecture(DSM), lecture(CIM)),
    )

    assert item.sources() == (DSM, CIM)
    assert item.ecart is None


def test_chaque_entree_du_registre_est_lue_deux_fois() -> None:
    """Le contrôle porte sur le contenu réel, pas seulement sur le type.

    Le validateur garantit qu'une entrée *peut* citer deux lectures ; ce test garantit que
    celles du Registre livré le font effectivement, et depuis deux nosographies et non
    deux paraphrases.
    """
    registre = registre_module_a_reduit()

    for entree in registre.entrees():
        assert len(entree.lectures) >= 2, entree.identifiant
        assert len(set(entree.sources())) == len(entree.sources()), entree.identifiant


def test_le_sommeil_est_un_item_dispute_et_le_dit() -> None:
    """L'écart entre nosographies est conservé, pas moyenné en silence.

    Le DSM-5-TR fait du sommeil un critère à part entière ; la CIM-11 le réunit à
    l'appétit dans sa liste MMS. Un entretien qui n'explore que le sommeil renseigne donc
    pleinement l'un et à moitié l'autre. C'est exactement le genre d'item sur lequel
    ADR-0003 demande de ne pas tirer de conclusions, et le Registre doit le dire.
    """
    entrees = {entree.identifiant: entree for entree in registre_module_a_reduit().entrees()}

    assert entrees["A3a"].est_disputee()
    assert "appétit" in (entrees["A3a"].ecart or "")

    # L'humeur et l'anhédonie sont les deux symptômes d'entrée des deux nosographies.
    assert not entrees["A1"].est_disputee()
    assert not entrees["A2"].est_disputee()


def test_aucun_libelle_du_mini_ne_figure_au_registre() -> None:
    """ADR-0002 : le dépôt porte la structure de l'instrument, jamais son expression.

    Contrôle grossier et volontairement conservateur — il ne peut pas reconnaître un
    libellé qu'il ne connaît pas. Il attrape la régression réaliste : quelqu'un qui, ayant
    obtenu une licence, recopierait les formulations dans le Registre « pour que ce soit
    plus clair ». Les sources citées sont des nosographies publiées, pas le MINI.
    """
    registre = registre_module_a_reduit()

    for entree in registre.entrees():
        for source in entree.sources():
            assert "M.I.N.I" not in source
            assert "Sheehan" not in source, (
                f"{entree.identifiant} cite l'instrument lui-même ; le Registre est "
                "reconstruit depuis la littérature nosographique (ADR-0003)"
            )
