"""La chaîne exécutée contre un modèle réel.

Hors de la suite par défaut : ces passages coûtent de l'argent, appellent le réseau et ne
sont pas déterministes. Ils ne mesurent pas non plus la qualité de détection — c'est le
rôle du benchmark. Ils vérifient une seule chose : que l'adaptateur réel se substitue à
l'adaptateur factice sans que rien au-dessus change.

    uv run pytest -m modele_reel
"""

import pytest

from minerva.corpus import Specification, generer
from minerva.detection import detecter
from minerva.domaine import Fiche, Locuteur, VerdictItem
from minerva.evaluation import EntretienEvalue, evaluer_par_provenance
from minerva.modele import AdaptateurAnthropic
from minerva.registre import registre_module_a_reduit

pytestmark = pytest.mark.modele_reel


def test_la_chaine_tourne_contre_un_modele_reel() -> None:
    registre = registre_module_a_reduit()
    specification = Specification(
        fiche_visee=Fiche(
            verdicts=[
                VerdictItem(identifiant="A1", sollicite=True, renseigne=True, empans=[]),
                VerdictItem(identifiant="A2", sollicite=True, renseigne=False, empans=[]),
                VerdictItem(identifiant="A3a", sollicite=False, renseigne=False, empans=[]),
                VerdictItem(identifiant="A_cadre", sollicite=True, renseigne=True, empans=[]),
            ]
        )
    )
    # Deux modèles distincts, comme l'exige ADR-0004 : un détecteur n'est jamais évalué
    # sur ce qu'il a lui-même écrit. Ils restent de la même famille, donc ce passage est
    # un score intra-famille — jamais une référence propre.
    generateur = AdaptateurAnthropic(modele="claude-haiku-4-5")
    detecteur = AdaptateurAnthropic()

    entretien = generer(specification, registre, generateur)
    prediction = detecter(entretien.retranscription, registre, detecteur)
    scores = evaluer_par_provenance(
        detecteur.identite,
        [
            EntretienEvalue(
                style=entretien.style,
                reference=entretien.reference,
                prediction=prediction,
                generateur=entretien.generateur,
            )
        ],
        registre,
    )

    assert entretien.retranscription.tours, "le modèle doit produire un entretien non vide"
    assert all(
        tour.locuteur in (Locuteur.CLINICIEN, Locuteur.PATIENT)
        for tour in entretien.retranscription.tours
    )
    assert prediction.identifiants() == entretien.reference.identifiants()
    # Aucune assertion sur la valeur : ce test garantit la mécanique, jamais la qualité.
    assert scores.intra_famille is not None
    assert 0.0 <= scores.intra_famille.renseigne.rappel <= 1.0
    assert scores.croise is None, "une seule famille en jeu : rien à croiser"
