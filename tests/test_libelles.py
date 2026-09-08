"""Les libellés officiels, fournis à l'exécution par un opérateur licencié.

Le dépôt ne les versionne pas et n'en dépend pas — ADR-0002. Ils servent à l'affichage
et à rien d'autre : entrés dans une décision de détection, ils feraient dépendre les
chiffres du dépôt d'un fichier que le dépôt n'a pas le droit de distribuer.
"""

import json
from pathlib import Path

import pytest

from minerva.affichage import decrire_fiche
from minerva.corpus import Specification, generer
from minerva.detection import detecter
from minerva.domaine import (
    Entretien,
    Fiche,
    Locuteur,
    Retranscription,
    TourDeParole,
    VerdictItem,
)
from minerva.evaluation import Mesures, evaluer
from minerva.libelles import Libelles, LibellesIllisibles, charger
from minerva.modele import AdaptateurFactice
from minerva.registre import registre_module_a_reduit


def ecrire(chemin: Path, contenu: object) -> Path:
    chemin.write_text(json.dumps(contenu, ensure_ascii=False), encoding="utf-8")
    return chemin


def test_un_fichier_de_libelles_est_charge_et_relu_par_identifiant(tmp_path: Path) -> None:
    """Le mécanisme qui permet un affichage officiel sans que le dépôt redistribue rien."""
    fichier = ecrire(tmp_path / "libelles.mini.json", {"A1": "Libellé officiel de A1."})

    libelles = charger(fichier)

    assert libelles.pour("A1") == "Libellé officiel de A1."


def test_sans_fichier_aucun_libelle_n_est_rendu() -> None:
    """L'absence est un état représentable, pas un cas qui plante plus loin.

    C'est le mode nominal du dépôt : personne n'a de licence, et la chaîne doit tourner.
    """
    assert Libelles.absentes().pour("A1") is None


def test_un_fichier_annonce_mais_illisible_est_signale(tmp_path: Path) -> None:
    """Se rabattre en silence sur l'absence donnerait le pire des deux mondes.

    L'opérateur croirait lire les formulations officielles et lirait des replis, sans
    qu'aucun signe ne l'en avertisse. Un fichier qu'on a désigné doit se charger ou se
    plaindre.
    """
    with pytest.raises(LibellesIllisibles, match="introuvable"):
        charger(tmp_path / "jamais-depose.mini.json")

    pas_du_json = tmp_path / "casse.mini.json"
    pas_du_json.write_text("{ceci n'est pas du json", encoding="utf-8")
    with pytest.raises(LibellesIllisibles, match="JSON"):
        charger(pas_du_json)

    with pytest.raises(LibellesIllisibles, match="objet"):
        charger(ecrire(tmp_path / "liste.mini.json", ["A1", "A2"]))

    with pytest.raises(LibellesIllisibles, match="A1"):
        charger(ecrire(tmp_path / "imbrique.mini.json", {"A1": {"fr": "Libellé."}}))


def test_un_fichier_plus_large_que_le_registre_reste_utilisable(tmp_path: Path) -> None:
    """Un fichier sous licence couvre les dix-sept Modules ; le Registre en porte deux.

    Refuser le surplus rendrait tout fichier réel inutilisable, et pousserait l'opérateur
    à tailler son fichier à la main pour faire plaisir au programme.
    """
    libelles = charger(
        ecrire(
            tmp_path / "complet.mini.json",
            {"A1": "Libellé de A1.", "P4": "Libellé d'un Module que le Registre ignore."},
        )
    )

    assert libelles.pour("A1") == "Libellé de A1."
    assert libelles.pour("P4") == "Libellé d'un Module que le Registre ignore."


LIBELLE_TEMOIN = "Formulation officielle sous licence, marqueur de fuite."
"""Une chaîne qu'on ne peut pas confondre : si elle apparaît dans un prompt, elle en vient."""


def chaine_complete(libelles: Libelles) -> tuple[str, list[str], Mesures]:
    """Déroule Spécification → Entretien → détection → chiffres, et affiche la Fiche.

    Rend l'affichage, tout ce qui a traversé la couture du port modèle, et les chiffres.
    """
    registre = registre_module_a_reduit()
    eteint = {
        ident: VerdictItem(identifiant=ident, sollicite=False, renseigne=False, empans=[])
        for ident in registre.identifiants()
    }
    specification = Specification(fiche_visee=Fiche(verdicts=list(eteint.values())))
    entretien_ecrit = Entretien(
        retranscription=Retranscription(
            tours=[
                TourDeParole(indice=0, locuteur=Locuteur.CLINICIEN, texte="Bonjour."),
                TourDeParole(indice=1, locuteur=Locuteur.PATIENT, texte="Bonjour."),
            ]
        ),
        reference=Fiche(verdicts=list(eteint.values())),
    )

    modele = AdaptateurFactice([entretien_ecrit, Fiche(verdicts=list(eteint.values()))])
    entretien = generer(specification, registre, modele)
    prediction = detecter(entretien.retranscription, registre, modele)

    return (
        decrire_fiche(prediction, registre, libelles),
        modele.prompts,
        evaluer([(entretien.reference, prediction)], registre),
    )


def test_aucun_libelle_n_atteint_jamais_le_modele() -> None:
    """Le cœur d'ADR-0002, vérifié à la seule couture qui puisse le montrer.

    `AdaptateurFactice.prompts` retient tout ce qui est passé au modèle. Si un libellé y
    figurait, les chiffres du dépôt dépendraient d'un fichier que le dépôt n'a pas le
    droit de distribuer, et deux opérateurs cesseraient de mesurer la même chose. C'est
    ce test, et non la relecture, qui tient la règle.
    """
    affichage, prompts, _ = chaine_complete(
        Libelles(par_identifiant={"A1": LIBELLE_TEMOIN, "A_cadre": LIBELLE_TEMOIN})
    )

    assert LIBELLE_TEMOIN in affichage, "le libellé doit bien servir, sinon le test ne prouve rien"
    assert prompts, "la chaîne doit avoir parlé au modèle, sinon l'absence est triviale"
    for prompt in prompts:
        assert LIBELLE_TEMOIN not in prompt


def test_la_chaine_rend_les_memes_chiffres_avec_et_sans_libelles() -> None:
    """Sans licence, le dépôt tourne — et avec, il mesure exactement pareil.

    Le premier point est le mode nominal du projet ; le second est ce qui rend les
    chiffres comparables d'un opérateur à l'autre. C'est `test_aucun_libelle_n_atteint_
    jamais_le_modele` qui détecte une fuite ; celui-ci fixe la conséquence attendue.
    """
    _, _, sans = chaine_complete(Libelles.absentes())
    _, _, avec = chaine_complete(Libelles(par_identifiant={"A1": LIBELLE_TEMOIN}))

    assert sans == avec
