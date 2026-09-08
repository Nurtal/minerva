"""L'affichage d'une Fiche à un humain — la seule chose que les libellés habillent.

Distinct de `rendu`, qui fabrique le texte destiné au modèle. La séparation est la
consigne d'ADR-0002 rendue structurelle : un libellé qui remonterait dans un prompt
ferait dépendre les chiffres d'un fichier que le dépôt n'a pas le droit de distribuer.
"""

from minerva.affichage import decrire_fiche
from minerva.domaine import EmpanDePreuve, Fiche, RoleEmpan, VerdictItem
from minerva.libelles import Libelles
from minerva.registre import registre_module_a_reduit


def fiche_simple() -> Fiche:
    return Fiche(
        verdicts=[
            VerdictItem(
                identifiant="A1",
                sollicite=True,
                renseigne=True,
                empans=[
                    EmpanDePreuve(
                        indice_tour=0,
                        role=RoleEmpan.SOLLICITATION,
                        passage="Comment est le moral",
                    ),
                    EmpanDePreuve(
                        indice_tour=1,
                        role=RoleEmpan.RENSEIGNEMENT,
                        passage="Au plus bas, depuis un mois",
                    ),
                ],
            ),
            VerdictItem(identifiant="A2", sollicite=True, renseigne=False, empans=[]),
            VerdictItem(identifiant="A3a", sollicite=False, renseigne=False, empans=[]),
            VerdictItem(identifiant="A_cadre", sollicite=False, renseigne=False, empans=[]),
        ]
    )


def test_le_libelle_officiel_habille_l_entree_quand_il_est_fourni() -> None:
    """Ce que l'opérateur licencié gagne : reconnaître l'item qu'il cote, à sa formulation."""
    texte = decrire_fiche(
        fiche_simple(),
        registre_module_a_reduit(),
        Libelles(par_identifiant={"A1": "Libellé officiel de A1."}),
    )

    assert "Libellé officiel de A1." in texte


def test_sans_libelle_l_entree_se_rabat_sur_son_construct_reconstruit() -> None:
    """Le mode nominal du dépôt : aucune licence, et la Fiche se lit quand même.

    Le construct reconstruit est ce que MINERVA mesure réellement — pas le libellé du
    MINI. Le montrer plutôt qu'un identifiant nu est le repli honnête.
    """
    texte = decrire_fiche(fiche_simple(), registre_module_a_reduit(), Libelles.absentes())

    assert "Humeur dépressive présente la majeure partie de la journée" in texte
    assert "Libellé officiel" not in texte


def test_l_affichage_parle_le_vocabulaire_du_glossaire() -> None:
    """Un humain lit « Sollicité », pas la valeur de sérialisation `sollicite`.

    Les valeurs d'énumération sont un format de transport : sans accent, parce qu'elles
    voyagent dans du JSON et des prompts. CONTEXT.md fixe en revanche les termes du
    domaine, et c'est lui que l'affichage doit parler.
    """
    texte = decrire_fiche(fiche_simple(), registre_module_a_reduit(), Libelles.absentes())

    assert "sollicité" in texte
    assert "renseigné" in texte
    assert "sollicite ·" not in texte


def test_une_entree_que_rien_ne_touche_le_dit_en_toutes_lettres() -> None:
    """L'oubli est un résultat, pas un blanc dans la page.

    C'est même le résultat intéressant : l'entrée que le Clinicien n'a pas sollicitée et
    que l'Entretien n'a pas renseignée. Une ligne vide se lirait comme un défaut
    d'affichage.
    """
    texte = decrire_fiche(fiche_simple(), registre_module_a_reduit(), Libelles.absentes())

    assert "A3a — ni sollicité ni renseigné" in texte


def test_un_module_ecarte_a_raison_s_affiche_non_applicable() -> None:
    """Le drapeau est dérivé du graphe, pas lu sur la Fiche.

    La porte du Module A est établie négative sur ses deux filtres : la suite du Module
    est écartée à raison. L'afficher évite qu'un Module correctement sauté se lise comme
    une série d'oublis — c'est toute la différence entre un reproche et un non-lieu.
    """
    fiche = Fiche(
        verdicts=[
            VerdictItem(
                identifiant=ident,
                sollicite=True,
                renseigne=True,
                empans=[EmpanDePreuve(indice_tour=1, role=RoleEmpan.RENSEIGNEMENT, passage="Non.")],
                positif=False,
            )
            for ident in ("A1", "A2")
        ]
        + [
            VerdictItem(identifiant="A3a", sollicite=False, renseigne=False, empans=[]),
            VerdictItem(identifiant="A_cadre", sollicite=False, renseigne=False, empans=[]),
        ]
    )

    texte = decrire_fiche(fiche, registre_module_a_reduit(), Libelles.absentes())

    assert "A3a — non-applicable" in texte
    assert "A_cadre — non-applicable" in texte
    # Les filtres eux-mêmes restent attendus : c'est la question d'entrée du Module.
    assert "A1 — sollicité · renseigné" in texte
