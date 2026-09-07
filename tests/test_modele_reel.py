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
from minerva.evaluation import evaluer
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
    # Le même modèle génère et détecte : ADR-0004 interdit d'en tirer une mesure, et ce
    # test n'en tire aucune — il vérifie la mécanique, pas la qualité. Le partitionnement
    # du corpus par générateur est le ticket dédié.
    modele = AdaptateurAnthropic()

    entretien = generer(specification, registre, modele)
    prediction = detecter(entretien.retranscription, registre, modele)
    mesures = evaluer([(entretien.reference, prediction)], registre)

    assert entretien.retranscription.tours, "le modèle doit produire un entretien non vide"
    assert all(
        tour.locuteur in (Locuteur.CLINICIEN, Locuteur.PATIENT)
        for tour in entretien.retranscription.tours
    )
    assert prediction.identifiants() == entretien.reference.identifiants()
    # Aucune assertion sur la valeur : ce serait une mesure, et elle serait contaminée.
    assert 0.0 <= mesures.renseigne.rappel <= 1.0
