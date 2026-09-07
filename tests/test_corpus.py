"""La génération part d'une Spécification et en dérive un Entretien.

La vérité terrain est vraie par construction — mais seulement si le modèle a bien
réalisé ce que la Spécification demandait. C'est ce que ce module vérifie.
"""

import pytest

from minerva.corpus import (
    GenerationInfidele,
    Specification,
    SpecificationIncoherente,
    generer,
)
from minerva.domaine import (
    EmpanDePreuve,
    Entretien,
    Fiche,
    Locuteur,
    Retranscription,
    RoleEmpan,
    TourDeParole,
    VerdictItem,
)
from minerva.modele import AdaptateurFactice
from minerva.registre import RegistreDItems, registre_module_a_reduit
from tests.fabriques import item


def specification(
    etats: dict[str, tuple[bool, bool]], polarites: dict[str, bool] | None = None
) -> Specification:
    """Une Spécification concise : identifiant -> (sollicite, renseigne), polarités à part.

    Prend un dictionnaire plutôt que des arguments nommés : un identifiant d'entrée du
    Registre n'a aucune raison d'être un identifiant Python valide.
    """
    polarites = polarites or {}
    return Specification(
        fiche_visee=Fiche(
            verdicts=[
                VerdictItem(
                    identifiant=ident,
                    sollicite=sol,
                    renseigne=ren,
                    positif=polarites.get(ident),
                    empans=[],
                )
                for ident, (sol, ren) in etats.items()
            ]
        )
    )


def entretien_genere(verdicts: list[VerdictItem], nombre_de_tours: int = 2) -> Entretien:
    return Entretien(
        retranscription=Retranscription(
            tours=[
                TourDeParole(
                    indice=indice,
                    locuteur=Locuteur.CLINICIEN if indice % 2 == 0 else Locuteur.PATIENT,
                    texte=f"tour {indice}",
                )
                for indice in range(nombre_de_tours)
            ]
        ),
        reference=Fiche(verdicts=verdicts),
    )


def test_la_reference_porte_un_verdict_par_item_du_registre() -> None:
    """La Fiche de référence a la forme du Registre, comme la sortie de détection."""
    registre = registre_module_a_reduit()
    genere = entretien_genere(
        [
            VerdictItem(
                identifiant="A1",
                sollicite=True,
                renseigne=True,
                empans=[
                    EmpanDePreuve(indice_tour=0, role=RoleEmpan.SOLLICITATION, passage="tour 0"),
                    EmpanDePreuve(indice_tour=1, role=RoleEmpan.RENSEIGNEMENT, passage="tour 1"),
                ],
            )
        ]
    )

    entretien = generer(
        specification(
            {
                "A1": (True, True),
                "A2": (False, False),
                "A3a": (False, False),
                "A_cadre": (False, False),
            }
        ),
        registre,
        AdaptateurFactice([genere]),
    )

    assert entretien.reference.identifiants() == set(registre.identifiants())


def test_un_entretien_qui_ne_realise_pas_la_specification_est_refuse() -> None:
    """Si le modèle n'a pas réalisé ce qui était demandé, la vérité terrain est fausse.

    Un corpus dont la référence ment est pire qu'un corpus absent : il produit des
    chiffres, et ces chiffres sont faux.
    """
    genere = entretien_genere(
        [VerdictItem(identifiant="A1", sollicite=False, renseigne=False, empans=[])]
    )

    with pytest.raises(GenerationInfidele, match="A1"):
        generer(
            specification(
                {
                    "A1": (True, True),
                    "A2": (False, False),
                    "A3a": (False, False),
                    "A_cadre": (False, False),
                }
            ),
            registre_module_a_reduit(),
            AdaptateurFactice([genere]),
        )


def test_un_empan_qui_designe_un_tour_inexistant_est_refuse() -> None:
    """Un Empan de preuve qui ne pointe sur rien n'est pas une preuve."""
    genere = entretien_genere(
        [
            VerdictItem(
                identifiant="A1",
                sollicite=True,
                renseigne=False,
                empans=[
                    EmpanDePreuve(indice_tour=99, role=RoleEmpan.SOLLICITATION, passage="tour 99")
                ],
            )
        ],
        nombre_de_tours=2,
    )

    with pytest.raises(GenerationInfidele, match="99"):
        generer(
            specification(
                {
                    "A1": (True, False),
                    "A2": (False, False),
                    "A3a": (False, False),
                    "A_cadre": (False, False),
                }
            ),
            registre_module_a_reduit(),
            AdaptateurFactice([genere]),
        )


def test_un_verdict_positif_sans_empan_est_refuse() -> None:
    """Une référence qui affirme sans montrer n'est pas une vérité terrain.

    Le refus vaut pour la référence, pas pour la prédiction : une détection qui affirme
    sans ancrer est une erreur mesurable — c'est ce que compte le taux d'ancrage — alors
    qu'une référence non ancrée rend l'ancrage inévaluable pour cet Item.
    """
    genere = entretien_genere(
        [VerdictItem(identifiant="A1", sollicite=True, renseigne=False, empans=[])]
    )

    with pytest.raises(GenerationInfidele, match="A1"):
        generer(
            specification(
                {
                    "A1": (True, False),
                    "A2": (False, False),
                    "A3a": (False, False),
                    "A_cadre": (False, False),
                }
            ),
            registre_module_a_reduit(),
            AdaptateurFactice([genere]),
        )


def registre_deux_modules() -> RegistreDItems:
    return RegistreDItems(
        items=[
            item("A1"),
            item("B1", module="B"),
        ]
    )


def test_un_entretien_est_une_seule_conversation_meme_avec_plusieurs_modules() -> None:
    """Un Entretien n'est pas une concaténation de bouts écrits séparément.

    Générer module par module puis recoller produirait des indices de Tour dupliqués —
    chaque passage renumérote à partir de zéro — et les Empans d'un Module pointeraient
    silencieusement sur les Tours d'un autre.
    """
    genere = Entretien(
        retranscription=Retranscription(
            tours=[
                TourDeParole(indice=0, locuteur=Locuteur.CLINICIEN, texte="Le moral ?"),
                TourDeParole(indice=1, locuteur=Locuteur.PATIENT, texte="Bas."),
                TourDeParole(indice=2, locuteur=Locuteur.CLINICIEN, texte="Des idées noires ?"),
                TourDeParole(indice=3, locuteur=Locuteur.PATIENT, texte="Non."),
            ]
        ),
        reference=Fiche(
            verdicts=[
                VerdictItem(
                    identifiant="A1",
                    sollicite=True,
                    renseigne=False,
                    empans=[
                        EmpanDePreuve(
                            indice_tour=0, role=RoleEmpan.SOLLICITATION, passage="Le moral"
                        )
                    ],
                ),
                VerdictItem(
                    identifiant="B1",
                    sollicite=True,
                    renseigne=False,
                    empans=[
                        EmpanDePreuve(
                            indice_tour=2, role=RoleEmpan.SOLLICITATION, passage="idées noires"
                        )
                    ],
                ),
            ]
        ),
    )

    entretien = generer(
        specification({"A1": (True, False), "B1": (True, False)}),
        registre_deux_modules(),
        AdaptateurFactice([genere]),
    )

    indices = [tour.indice for tour in entretien.retranscription.tours]
    assert indices == sorted(set(indices)), "les indices de Tour doivent être uniques et ordonnés"
    assert entretien.reference.identifiants() == {"A1", "B1"}


def test_un_empan_de_sollicitation_sur_un_tour_du_patient_est_refuse() -> None:
    """Seul le Clinicien sollicite ; seul le Patient renseigne.

    Un Empan mal typé rend la vérité terrain fausse là où elle prétend être vraie par
    construction — et le taux d'ancrage mesurerait alors n'importe quoi.
    """
    genere = entretien_genere(
        [
            VerdictItem(
                identifiant="A1",
                sollicite=True,
                renseigne=False,
                empans=[
                    EmpanDePreuve(indice_tour=1, role=RoleEmpan.SOLLICITATION, passage="tour 1")
                ],
            )
        ]
    )

    with pytest.raises(GenerationInfidele, match="patient"):
        generer(
            specification(
                {
                    "A1": (True, False),
                    "A2": (False, False),
                    "A3a": (False, False),
                    "A_cadre": (False, False),
                }
            ),
            registre_module_a_reduit(),
            AdaptateurFactice([genere]),
        )


def test_une_specification_qui_ne_couvre_pas_le_registre_est_refusee() -> None:
    """Un Item absent de la Spécification n'est pas un Item non visé, c'est une commande trouée."""
    genere = entretien_genere([])

    with pytest.raises(SpecificationIncoherente, match="A3a"):
        generer(
            specification({"A1": (False, False), "A2": (False, False)}),
            registre_module_a_reduit(),
            AdaptateurFactice([genere]),
        )


def test_un_empan_dont_le_passage_ne_figure_pas_dans_le_tour_est_refuse() -> None:
    """Un passage recopié de travers n'est pas une preuve, c'est une citation inventée.

    C'est le contrôle que la dénormalisation rend possible : tant que l'Empan ne portait
    que l'indice du Tour, rien ne permettait de dire qu'il montrait bien quelque chose.
    """
    genere = entretien_genere(
        [
            VerdictItem(
                identifiant="A1",
                sollicite=True,
                renseigne=False,
                empans=[
                    EmpanDePreuve(
                        indice_tour=0,
                        role=RoleEmpan.SOLLICITATION,
                        passage="ce que le clinicien n'a jamais dit",
                    )
                ],
            )
        ]
    )

    with pytest.raises(GenerationInfidele, match="ne figure pas"):
        generer(
            specification(
                {
                    "A1": (True, False),
                    "A2": (False, False),
                    "A3a": (False, False),
                    "A_cadre": (False, False),
                }
            ),
            registre_module_a_reduit(),
            AdaptateurFactice([genere]),
        )


def test_une_polarite_sur_un_item_non_filtre_est_ecartee_de_la_reference() -> None:
    """ADR-0006 vaut aux deux frontières, pas seulement à celle de la détection.

    Une Fiche de référence qui porterait une polarité sur un Item de symptôme serait une
    cotation stockée — ce que l'ADR-0001 interdit et que l'ADR-0006 n'excepte que pour les
    Items filtres.
    """
    genere = entretien_genere(
        [VerdictItem(identifiant="A3a", sollicite=False, renseigne=False, positif=True, empans=[])]
    )

    entretien = generer(
        specification(
            {
                "A1": (False, False),
                "A2": (False, False),
                "A3a": (False, False),
                "A_cadre": (False, False),
            }
        ),
        registre_module_a_reduit(),
        AdaptateurFactice([genere]),
    )

    assert entretien.reference.par_identifiant()["A3a"].positif is None


def entretien_avec(identifiant: str, positif: bool | None) -> Entretien:
    return entretien_genere(
        [
            VerdictItem(
                identifiant=identifiant,
                sollicite=True,
                renseigne=True,
                positif=positif,
                empans=[
                    EmpanDePreuve(indice_tour=0, role=RoleEmpan.SOLLICITATION, passage="tour 0"),
                    EmpanDePreuve(indice_tour=1, role=RoleEmpan.RENSEIGNEMENT, passage="tour 1"),
                ],
            )
        ]
    )


def test_la_polarite_commandee_par_la_specification_est_verifiee() -> None:
    """Sans ce contrôle, la seconde jambe de la double dérivation n'a pas de vérité terrain.

    La Spécification commande un filtre négatif ; le modèle rend un filtre positif. Si on
    laissait passer, le graphe déroulé sur la référence dirait autre chose que ce qui a été
    commandé, et l'écart mesuré côté prédiction ne voudrait plus rien dire.
    """
    with pytest.raises(GenerationInfidele, match="polarité"):
        generer(
            specification(
                {
                    "A1": (True, True),
                    "A2": (False, False),
                    "A3a": (False, False),
                    "A_cadre": (False, False),
                },
                polarites={"A1": False},
            ),
            registre_module_a_reduit(),
            AdaptateurFactice([entretien_avec("A1", positif=True)]),
        )


def test_la_reference_porte_la_polarite_commandee() -> None:
    """Ce qui rend le graphe déroulable sur la référence de bout en bout."""
    entretien = generer(
        specification(
            {
                "A1": (True, True),
                "A2": (False, False),
                "A3a": (False, False),
                "A_cadre": (False, False),
            },
            polarites={"A1": False},
        ),
        registre_module_a_reduit(),
        AdaptateurFactice([entretien_avec("A1", positif=False)]),
    )

    assert entretien.reference.par_identifiant()["A1"].positif is False
