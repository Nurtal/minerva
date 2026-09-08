"""Les formulations officielles du MINI, fournies à l'exécution — jamais versionnées.

ADR-0002 : le texte du MINI ne peut pas entrer dans le dépôt. Un opérateur disposant
d'une licence dépose son propre fichier au lancement et obtient un affichage aux
formulations officielles, sans que le projet redistribue quoi que ce soit.

C'est aussi ici que se lit la désignation faite au lancement : `depuis_l_environnement`
est le seul endroit du dépôt qui consulte l'environnement du processus, et il le fait
faute de racine de composition — le projet n'a pas d'exécutable, #1 les mettant hors
périmètre.

Ce module ne sert que l'affichage. Un libellé qui remonterait dans un prompt ferait
dépendre les chiffres du dépôt d'un fichier que le dépôt n'a pas le droit de distribuer,
et deux opérateurs ne mesureraient plus la même chose. C'est pourquoi rien ici n'est
importé par `rendu`, `detection` ni `corpus`.
"""

import json
import os
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel

VARIABLE_LIBELLES = "MINERVA_LIBELLES"
"""La variable d'environnement où un opérateur licencié désigne son fichier.

Le démarrage d'un processus, et non une interface : le dépôt n'en a aucune, et #1 les
met hors périmètre. C'est le mécanisme le plus léger par lequel « fourni au lancement »
puisse être autre chose qu'une phrase du README.
"""


class LibellesIllisibles(ValueError):
    """Un fichier de libellés a été désigné mais ne peut pas être lu.

    Distinct de l'absence de fichier, et c'est tout l'intérêt : ne pas avoir de
    licence est le mode nominal, tandis qu'un fichier désigné et illisible est une
    erreur d'exploitation que seul l'opérateur peut corriger.
    """


class Libelles(BaseModel):
    """Les libellés dont on dispose, indexés par identifiant d'entrée du Registre.

    Vides tant qu'aucun fichier n'est fourni, ce qui est le mode nominal du dépôt : le
    projet doit tourner sans licence, et l'absence de libellé se lit comme une absence,
    jamais comme une erreur.
    """

    par_identifiant: Mapping[str, str] = {}
    """La table, annoncée en `Mapping` : sans `__setitem__`, le typage refuse d'y écrire.

    Pas de `frozen` sur ce modèle, contrairement à `IdentiteModele` ou `Panel` : ceux-là
    portent des valeurs et des tuples, là où une table de libellés reste un dictionnaire.
    Un `frozen` par-dessus ne gèlerait que la réaffectation du champ, laisserait passer
    la mutation du dictionnaire lui-même, et prétendrait de surcroît que le modèle est
    hachable — ce qui lèverait à la première tentative. La promesse est donc portée là où
    elle se vérifie, au typage, plutôt qu'affichée là où elle ne tient pas.
    """

    @classmethod
    def absentes(cls) -> "Libelles":
        """Le cas sans fichier, nommé plutôt que sous-entendu."""
        return cls()

    def pour(self, identifiant: str) -> str | None:
        """Le libellé officiel de cette entrée, ou `None` si on ne l'a pas.

        `None` plutôt qu'une chaîne vide ou l'identifiant : l'affichage doit pouvoir
        choisir son repli, et une chaîne vide se confondrait avec un libellé blanc.
        """
        return self.par_identifiant.get(identifiant)


def charger(chemin: Path) -> Libelles:
    """Lit un fichier de libellés déposé par un opérateur licencié.

    Un objet JSON plat, identifiant d'entrée vers formulation officielle.

    Se plaint plutôt que de se rabattre sur l'absence : l'opérateur qui a désigné un
    fichier croirait lire les formulations officielles alors qu'il lirait des replis, et
    rien à l'écran ne l'en avertirait. L'absence de fichier se dit `Libelles.absentes()`,
    et elle se dit à l'appel, pas par accident.

    Un identifiant que le Registre ne connaît pas est accepté sans bruit : un fichier
    sous licence couvre les dix-sept Modules du MINI là où le Registre n'en porte que
    deux, et refuser le surplus rendrait tout fichier réel inutilisable.
    """
    try:
        brut = chemin.read_text(encoding="utf-8")
    except FileNotFoundError as absent:
        raise LibellesIllisibles(f"fichier de libellés introuvable : {chemin}") from absent
    except OSError as illisible:
        raise LibellesIllisibles(
            f"fichier de libellés illisible : {chemin} ({illisible.strerror})"
        ) from illisible

    try:
        contenu = json.loads(brut)
    except json.JSONDecodeError as malforme:
        raise LibellesIllisibles(f"{chemin} n'est pas du JSON valide : {malforme}") from malforme

    if not isinstance(contenu, dict):
        raise LibellesIllisibles(
            f"{chemin} doit porter un objet JSON plat — identifiant vers libellé — "
            f"et non {type(contenu).__name__}"
        )

    non_textuels = sorted(
        identifiant for identifiant, libelle in contenu.items() if not isinstance(libelle, str)
    )
    if non_textuels:
        raise LibellesIllisibles(
            f"{chemin} : un libellé doit être une chaîne, ce qui n'est pas le cas de "
            f"{', '.join(non_textuels)}"
        )

    return Libelles(par_identifiant=contenu)


def depuis_l_environnement() -> Libelles:
    """Les libellés désignés au lancement, s'il y en a.

    Variable absente : personne n'a de licence, et c'est le mode nominal du dépôt — on
    rend `Libelles.absentes()` sans rien dire.

    Variable posée mais vide : ce n'est pas la même chose, et les confondre coûterait
    cher. `export MINERVA_LIBELLES=$CHEMIN` avec `$CHEMIN` non défini laisse une variable
    posée et vide ; l'opérateur croit avoir désigné ses libellés et lirait des replis
    sans qu'aucun signe ne l'en avertisse. C'est le même refus que dans `charger`, appuyé
    plus fort : un chemin posé dans l'environnement se relit rarement.
    """
    designe = os.environ.get(VARIABLE_LIBELLES)
    if designe is None:
        return Libelles.absentes()

    # Normalisé une seule fois, puis utilisé tel quel : contrôler la valeur rognée et
    # ouvrir la valeur brute ferait échouer « MINERVA_LIBELLES=" f.json " » sur un chemin
    # dont les espaces sont invisibles à l'écran. Un fichier réellement nommé avec des
    # espaces de bord devient de ce fait inatteignable par cette variable ; l'espace
    # accidentel — une fin de ligne, un `.env` généreux — est mille fois plus fréquent.
    designe = designe.strip()
    if not designe:
        raise LibellesIllisibles(
            f"{VARIABLE_LIBELLES} est posée mais vide : désigner un fichier de libellés "
            "et n'en nommer aucun laisserait lire des replis à qui croit lire les "
            f"formulations officielles. Nommez le fichier, ou retirez {VARIABLE_LIBELLES}"
        )
    return charger(Path(designe))
