"""Les libellés officiels, fournis à l'exécution par un opérateur licencié.

Le dépôt ne les versionne pas et n'en dépend pas — ADR-0002. Ils servent à l'affichage
et à rien d'autre : entrés dans une décision de détection, ils feraient dépendre les
chiffres du dépôt d'un fichier que le dépôt n'a pas le droit de distribuer.
"""

import ast
import json
from pathlib import Path

import pytest

import minerva
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
from minerva.libelles import (
    VARIABLE_LIBELLES,
    Libelles,
    LibellesIllisibles,
    charger,
    depuis_l_environnement,
)
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
    """Le témoin ne traverse pas la couture du port modèle.

    Ce que ce test vaut, exactement : `chaine_complete` ne remet les `Libelles` qu'à
    `decrire_fiche`, et ni `generer` ni `detecter` n'ont de paramètre qui puisse en
    porter. La boucle ne peut donc échouer qu'après un changement de signature qui
    obligerait de toute façon à rouvrir ce fichier. C'est un filet, pas la garantie.

    La garantie est dans le graphe des imports, et c'est
    `test_aucun_module_de_la_chaine_n_importe_les_libelles` qui la tient : il échoue si
    un module de la chaîne se met à charger des libellés lui-même, ce que celui-ci ne
    verrait pas puisqu'il passe un objet et jamais un chemin.
    """
    affichage, prompts, _ = chaine_complete(
        Libelles(par_identifiant={"A1": LIBELLE_TEMOIN, "A_cadre": LIBELLE_TEMOIN})
    )

    assert LIBELLE_TEMOIN in affichage, "le libellé doit bien servir, sinon le test ne prouve rien"
    assert prompts, "la chaîne doit avoir parlé au modèle, sinon l'absence est triviale"
    for prompt in prompts:
        assert LIBELLE_TEMOIN not in prompt


def test_la_chaine_tourne_et_mesure_sans_le_moindre_libelle() -> None:
    """Le mode nominal du dépôt : personne n'a de licence, et les chiffres sortent.

    C'est la moitié falsifiable du critère « en l'absence de ce fichier, la chaîne
    fonctionne à l'identique » : elle tomberait si la chaîne acquérait une dépendance
    dure au fichier. L'autre moitié — « les mêmes chiffres » — est vraie par
    construction, `generer` et `detecter` ne prenant aucun libellé.
    """
    affichage, prompts, mesures = chaine_complete(Libelles.absentes())

    assert prompts, "la chaîne doit avoir tourné de bout en bout"
    assert mesures.renseigne.items_ecartes, "des chiffres ont bien été produits"
    assert "Humeur dépressive" in affichage, "le repli sur le construct habille la Fiche"


def test_les_memes_chiffres_avec_et_sans_libelles() -> None:
    """Ce que ce test vaut, exactement : peu, et il faut le dire.

    L'adaptateur factice rejoue un script sans regarder le prompt, donc les chiffres
    seraient identiques même si un libellé fuyait dans un prompt — ce test ne détecte
    pas cette fuite-là, `test_aucun_module_de_la_chaine_n_importe_les_libelles` s'en
    charge. Il reste sensible au cas où l'on ferait entrer des libellés ailleurs que
    dans le prompt, dans `detecter` ou `evaluer`, et c'est à ce titre qu'il est gardé.
    """
    _, _, sans = chaine_complete(Libelles.absentes())
    _, _, avec = chaine_complete(Libelles(par_identifiant={"A1": LIBELLE_TEMOIN}))

    assert sans == avec


def modules_importes(nom: str) -> set[str]:
    """Les modules qu'importe un module de `minerva`, lus dans sa syntaxe.

    Par l'arbre syntaxique et non par une recherche de texte : « libellé » apparaît dans
    la prose de plusieurs docstrings du paquet, et un test qui confondrait la mention
    avec l'import se déclencherait sur un commentaire.
    """
    chemin = Path(minerva.__file__).parent / f"{nom}.py"
    importes: set[str] = set()
    for noeud in ast.walk(ast.parse(chemin.read_text(encoding="utf-8"))):
        if isinstance(noeud, ast.Import):
            importes |= {alias.name for alias in noeud.names}
        elif isinstance(noeud, ast.ImportFrom) and noeud.module is not None:
            importes.add(noeud.module)
    return importes


def test_aucun_module_de_la_chaine_n_importe_les_libelles() -> None:
    """La vraie garantie d'ADR-0002 : la règle est lisible dans le graphe des imports.

    Un module qui ne connaît pas `libelles` ne peut pas en faire entrer dans un prompt,
    ni aller en charger un depuis un chemin convenu — ce qu'un test passant un objet ne
    verrait jamais. Celui-ci échoue à la ligne d'import, avant même qu'on se demande ce
    que le module compte en faire.

    `affichage` est visé au même titre : il est le seul à connaître les libellés, et
    l'importer depuis la chaîne les y ferait entrer par la bande.
    """
    for nom in ("corpus", "detection", "evaluation", "registre", "rendu", "domaine", "modele"):
        importes = modules_importes(nom)

        assert "minerva.libelles" not in importes, f"{nom} importe les libellés"
        assert "minerva.affichage" not in importes, f"{nom} importe l'affichage"


def test_sans_variable_d_environnement_on_tourne_sans_libelles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le mode nominal, obtenu sans que personne ait à le demander.

    C'est l'état de quiconque n'a pas de licence : la variable n'est pas posée, et la
    chaîne doit démarrer comme si de rien n'était.
    """
    monkeypatch.delenv(VARIABLE_LIBELLES, raising=False)

    assert depuis_l_environnement() == Libelles.absentes()


def test_le_fichier_designe_au_lancement_est_charge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ce que gagne l'opérateur licencié : poser une variable, et rien d'autre à câbler."""
    fichier = ecrire(tmp_path / "libelles_mini_7.0.2_fr.json", {"A1": "Libellé officiel de A1."})
    monkeypatch.setenv(VARIABLE_LIBELLES, str(fichier))

    assert depuis_l_environnement().pour("A1") == "Libellé officiel de A1."


def test_une_variable_qui_designe_un_fichier_absent_se_plaint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Poser la variable est une intention ; l'ignorer en silence la trahirait.

    C'est la même règle que pour `charger`, et elle vaut d'autant plus ici : un chemin
    posé dans l'environnement se relit rarement, et le repli passerait inaperçu bien plus
    longtemps qu'un appel explicite.
    """
    monkeypatch.setenv(VARIABLE_LIBELLES, str(tmp_path / "jamais-depose.mini.json"))

    with pytest.raises(LibellesIllisibles, match="introuvable"):
        depuis_l_environnement()


def test_une_variable_posee_mais_vide_est_une_intention_trahie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`export MINERVA_LIBELLES=$CHEMIN` avec `$CHEMIN` non défini : posée, et vide.

    Distinguer ce cas de la variable absente est tout l'intérêt : ne rien dire ferait
    lire des replis à qui a cru désigner ses libellés officiels. Le message doit nommer
    la variable, faute de quoi il parle d'un chemin que l'opérateur n'a jamais écrit.
    """
    for vide in ("", "   "):
        monkeypatch.setenv(VARIABLE_LIBELLES, vide)

        with pytest.raises(LibellesIllisibles, match=VARIABLE_LIBELLES):
            depuis_l_environnement()
