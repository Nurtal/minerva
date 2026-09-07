"""Le test de plus haut niveau : de la Spécification aux chiffres, en un passage.

C'est le seul test qui vérifie la contrainte de forme — que la sortie de détection est
comparable à la Fiche de référence et que l'évaluation est un diff. Cette propriété casse
silencieusement et n'est visible qu'à ce niveau.

Tout passe par l'adaptateur factice : aucun réseau, aucun coût, résultat déterministe.
Ce test garantit la mécanique, pas la qualité de détection — celle-ci relève du benchmark.
"""

from minerva.corpus import Specification, generer
from minerva.detection import detecter
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
from minerva.evaluation import evaluer
from minerva.modele import AdaptateurFactice
from minerva.registre import registre_module_a_reduit

SOLLICITATION = RoleEmpan.SOLLICITATION
RENSEIGNEMENT = RoleEmpan.RENSEIGNEMENT


def test_de_la_specification_aux_chiffres() -> None:
    """Chaîne complète sur un Entretien, avec des chiffres calculés à la main.

    La Spécification commande A1 sollicité et renseigné, A2 sollicité sans réponse
    exploitable, A3a non abordé. La détection retrouve tout sauf qu'elle croit A2
    renseigné : un faux positif.

    Le cadre temporel du module n'est jamais établi non plus, ce qui est un entretien
    imparfait mais parfaitement représentable.

    Sollicité — A1 et A2 justes ; A3a et A_cadre écartés faute de positif. Macro = 1.
    Renseigné — A1 juste (F1 1), A2 faux positif (F1 0), A3a et A_cadre écartés. Macro = 1/2.
    Ancrage  — trois verdicts justes, tous ancrés au bon tour. Le faux positif sur A2
               n'entre pas au dénominateur. Taux = 1.
    """
    registre = registre_module_a_reduit()

    specification = Specification(
        fiche_visee=Fiche(
            verdicts=[
                VerdictItem(identifiant="A1", sollicite=True, renseigne=True, empans=[]),
                VerdictItem(identifiant="A2", sollicite=True, renseigne=False, empans=[]),
                VerdictItem(identifiant="A3a", sollicite=False, renseigne=False, empans=[]),
                VerdictItem(identifiant="A_cadre", sollicite=False, renseigne=False, empans=[]),
            ]
        )
    )

    entretien_ecrit = Entretien(
        retranscription=Retranscription(
            tours=[
                TourDeParole(indice=0, locuteur=Locuteur.CLINICIEN, texte="Comment est le moral ?"),
                TourDeParole(
                    indice=1, locuteur=Locuteur.PATIENT, texte="Au plus bas, depuis un mois."
                ),
                TourDeParole(
                    indice=2, locuteur=Locuteur.CLINICIEN, texte="Et le plaisir aux choses ?"
                ),
                TourDeParole(indice=3, locuteur=Locuteur.PATIENT, texte="Je ne sais pas trop."),
            ]
        ),
        reference=Fiche(
            verdicts=[
                VerdictItem(
                    identifiant="A1",
                    sollicite=True,
                    renseigne=True,
                    empans=[
                        EmpanDePreuve(
                            indice_tour=0, role=SOLLICITATION, passage="Comment est le moral"
                        ),
                        EmpanDePreuve(
                            indice_tour=1, role=RENSEIGNEMENT, passage="Au plus bas, depuis un mois"
                        ),
                    ],
                ),
                VerdictItem(
                    identifiant="A2",
                    sollicite=True,
                    renseigne=False,
                    empans=[
                        EmpanDePreuve(
                            indice_tour=2, role=SOLLICITATION, passage="le plaisir aux choses"
                        )
                    ],
                ),
                VerdictItem(identifiant="A3a", sollicite=False, renseigne=False, empans=[]),
                VerdictItem(identifiant="A_cadre", sollicite=False, renseigne=False, empans=[]),
            ]
        ),
    )

    fiche_detectee = Fiche(
        verdicts=[
            VerdictItem(
                identifiant="A1",
                sollicite=True,
                renseigne=True,
                empans=[
                    EmpanDePreuve(
                        indice_tour=0, role=SOLLICITATION, passage="Comment est le moral"
                    ),
                    EmpanDePreuve(
                        indice_tour=1, role=RENSEIGNEMENT, passage="Au plus bas, depuis un mois"
                    ),
                ],
            ),
            VerdictItem(
                identifiant="A2",
                sollicite=True,
                renseigne=True,
                empans=[
                    EmpanDePreuve(
                        indice_tour=2, role=SOLLICITATION, passage="le plaisir aux choses"
                    ),
                    EmpanDePreuve(indice_tour=3, role=RENSEIGNEMENT, passage="Je ne sais pas trop"),
                ],
            ),
        ]
    )

    modele = AdaptateurFactice([entretien_ecrit, fiche_detectee])

    entretien = generer(specification, registre, modele)
    prediction = detecter(entretien.retranscription, registre, modele)
    mesures = evaluer([(entretien.reference, prediction)], registre)

    assert prediction.identifiants() == entretien.reference.identifiants()
    assert mesures.sollicite.f1 == 1.0
    assert mesures.renseigne.f1 == 0.5
    assert mesures.renseigne.items_ecartes == ("A3a", "A_cadre")
    assert mesures.taux_ancrage == 1.0
