"""La détection lit une Retranscription et un Registre, et rend une Fiche.

Tout passe par le port modèle, seul point substituable du système. L'adaptateur
factice rejoue des sorties structurées scriptées, ce qui rend ces tests hermétiques.
"""

import pytest

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
from minerva.modele import AdaptateurFactice, ReponseIncoherente
from minerva.registre import registre_module_a_reduit


def retranscription() -> Retranscription:
    return Retranscription(
        tours=[
            TourDeParole(indice=0, locuteur=Locuteur.CLINICIEN, texte="Comment est votre moral ?"),
            TourDeParole(indice=1, locuteur=Locuteur.PATIENT, texte="Très bas depuis un mois."),
        ]
    )


def test_la_detection_rend_les_verdicts_produits_par_le_modele() -> None:
    registre = registre_module_a_reduit()
    attendu = Fiche(
        verdicts=[
            VerdictItem(
                identifiant="A1",
                sollicite=True,
                renseigne=True,
                empans=[
                    EmpanDePreuve(indice_tour=0, role=RoleEmpan.SOLLICITATION),
                    EmpanDePreuve(indice_tour=1, role=RoleEmpan.RENSEIGNEMENT),
                ],
            )
        ]
    )

    fiche = detecter(retranscription(), registre, AdaptateurFactice([attendu]))

    assert fiche.par_identifiant()["A1"].sollicite is True
    assert fiche.par_identifiant()["A1"].renseigne is True


def test_la_fiche_rendue_porte_un_verdict_par_item_du_registre() -> None:
    """La contrainte de forme : la sortie a la forme du Registre, quoi que rende le modèle.

    Un Item que le modèle n'a pas mentionné n'est pas absent, il est négatif — sans quoi
    l'évaluation ne serait plus un diff entre deux objets de même forme.
    """
    registre = registre_module_a_reduit()

    fiche = detecter(retranscription(), registre, AdaptateurFactice([Fiche(verdicts=[])]))

    assert fiche.identifiants() == set(registre.identifiants())
    assert all(not verdict.sollicite and not verdict.renseigne for verdict in fiche.verdicts)


def test_un_item_hors_registre_rendu_par_le_modele_est_rejete() -> None:
    """Le modèle ne décide pas du périmètre : le Registre le fait."""
    hallucination = Fiche(
        verdicts=[VerdictItem(identifiant="Z9", sollicite=True, renseigne=True, empans=[])]
    )

    fiche = detecter(
        retranscription(), registre_module_a_reduit(), AdaptateurFactice([hallucination])
    )

    assert "Z9" not in fiche.identifiants()


def test_l_adaptateur_factice_refuse_une_reponse_du_mauvais_type() -> None:
    """Un scénario mal écrit doit échouer bruyamment, pas produire un résultat trompeur."""
    adaptateur = AdaptateurFactice([Retranscription(tours=[])])

    with pytest.raises(ReponseIncoherente):
        detecter(retranscription(), registre_module_a_reduit(), adaptateur)
