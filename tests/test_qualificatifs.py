"""Le Qualificatif : une entrée du Registre de portée Module, dont ses Items héritent.

Un cadre temporel établi une seule fois en ouverture rend cotables les Items du Module —
c'est la conduite d'entretien correcte, et le MINI lui-même présente le cadre en tête de
module « à relire aussi souvent que nécessaire ». Un Entretien qui ne l'établit jamais a un
défaut réel, que le Qualificatif rend visible au lieu de le laisser disparaître.
"""

import pytest

from minerva.corpus import GenerationInfidele, Specification, generer
from minerva.detection import detecter
from minerva.domaine import (
    EmpanDePreuve,
    Fiche,
    Locuteur,
    Retranscription,
    RoleEmpan,
    TourDeParole,
    VerdictItem,
)
from minerva.evaluation import evaluer
from minerva.modele import AdaptateurFactice
from minerva.registre import Qualificatif, RegistreDItems
from tests.fabriques import item


def registre() -> RegistreDItems:
    return RegistreDItems(
        items=[item("A1"), item("A2"), item("B1", module="B")],
        qualificatifs=[
            Qualificatif(
                identifiant="A_cadre",
                module="A",
                construct_sonde="ancienneté des troubles : au moins deux semaines",
                source="test",
            )
        ],
    )


def verdict(identifiant: str, renseigne: bool) -> VerdictItem:
    return VerdictItem(
        identifiant=identifiant,
        sollicite=renseigne,
        renseigne=renseigne,
        empans=[EmpanDePreuve(indice_tour=0, role=RoleEmpan.RENSEIGNEMENT, passage="p")]
        if renseigne
        else [],
    )


def test_un_qualificatif_est_une_entree_du_registre_au_meme_titre_qu_un_item() -> None:
    """Il apparaît dans la forme de la Fiche, donc dans la sortie de détection."""
    assert "A_cadre" in registre().identifiants()


def test_un_item_n_est_cotable_que_si_le_cadre_de_son_module_est_etabli() -> None:
    """Le contenu ne suffit pas : sans ancienneté, l'item n'est pas cotable selon le MINI."""
    fiche = Fiche(
        verdicts=[
            verdict("A1", renseigne=True),
            verdict("A2", renseigne=True),
            verdict("A_cadre", renseigne=False),
        ]
    )

    assert registre().renseignes_effectifs(fiche) == set()


def test_le_cadre_etabli_une_fois_rend_cotables_les_items_renseignes_du_module() -> None:
    """Le cas normal : le clinicien demande l'ancienneté une seule fois, en ouverture."""
    fiche = Fiche(
        verdicts=[
            verdict("A1", renseigne=True),
            verdict("A2", renseigne=False),
            verdict("A_cadre", renseigne=True),
        ]
    )

    assert registre().renseignes_effectifs(fiche) == {"A1", "A_cadre"}


def test_un_module_sans_qualificatif_ne_subit_aucun_heritage() -> None:
    """Le Module B n'en a pas : ses Items valent ce que la détection en dit, sans condition."""
    fiche = Fiche(verdicts=[verdict("B1", renseigne=True), verdict("A_cadre", renseigne=False)])

    assert "B1" in registre().renseignes_effectifs(fiche)


def test_la_detection_rend_un_verdict_pour_le_qualificatif() -> None:
    """Le Qualificatif se sollicite et se renseigne comme un Item, et la sortie le dit."""
    rendu = Fiche(
        verdicts=[
            VerdictItem(
                identifiant="A_cadre",
                sollicite=True,
                renseigne=True,
                empans=[
                    EmpanDePreuve(indice_tour=0, role=RoleEmpan.SOLLICITATION, passage="depuis"),
                    EmpanDePreuve(indice_tour=1, role=RoleEmpan.RENSEIGNEMENT, passage="un mois"),
                ],
            )
        ]
    )

    fiche = detecter(retranscription(), registre(), AdaptateurFactice([rendu, Fiche(verdicts=[])]))

    assert fiche.par_identifiant()["A_cadre"].renseigne is True


def test_un_cadre_jamais_etabli_se_lit_dans_la_sortie() -> None:
    """Le défaut ne disparaît pas : il apparaît comme un Qualificatif non Renseigné.

    Sans cette entrée, un entretien qui n'établit jamais l'ancienneté des troubles serait
    indiscernable d'un entretien correct.
    """
    fiche = detecter(
        retranscription(),
        registre(),
        AdaptateurFactice([Fiche(verdicts=[]), Fiche(verdicts=[])]),
    )

    assert fiche.par_identifiant()["A_cadre"].renseigne is False
    assert fiche.identifiants() == set(registre().identifiants())


def retranscription() -> Retranscription:
    return Retranscription(
        tours=[
            TourDeParole(indice=0, locuteur=Locuteur.CLINICIEN, texte="Depuis quand ?"),
            TourDeParole(indice=1, locuteur=Locuteur.PATIENT, texte="Un mois."),
        ]
    )


def test_la_specification_doit_fixer_l_etat_vise_du_qualificatif() -> None:
    """Le Qualificatif est une entrée du Registre : la commande doit le couvrir comme le reste."""
    with pytest.raises(GenerationInfidele, match="A_cadre"):
        generer(
            Specification(
                fiche_visee=Fiche(
                    verdicts=[
                        VerdictItem(identifiant=ident, sollicite=False, renseigne=False, empans=[])
                        for ident in ("A1", "A2", "B1")
                    ]
                )
            ),
            registre(),
            AdaptateurFactice([Fiche(verdicts=[])]),
        )


def test_le_contenu_obtenu_sans_cadre_etabli_est_rapporte_comme_non_cotable() -> None:
    """Le défaut que le Qualificatif existe pour rendre visible.

    Le clinicien a obtenu le contenu des deux items, mais n'a jamais demandé depuis quand.
    Rien de tout cela n'est cotable selon le MINI, et c'est un reproche distinct de l'oubli :
    les questions ont été posées, c'est le cadre qui manque.
    """
    fiche = Fiche(
        verdicts=[
            verdict("A1", renseigne=True),
            verdict("A2", renseigne=True),
            verdict("B1", renseigne=True),
            verdict("A_cadre", renseigne=False),
        ]
    )

    mesures = evaluer([(fiche, fiche)], registre())

    assert mesures.conduite.non_cotables_faute_de_cadre == {"A1": 1, "A2": 1}
