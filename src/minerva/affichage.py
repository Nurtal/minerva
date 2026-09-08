"""Comment on présente une Fiche à un humain. Aucun appel de modèle.

Distinct de `rendu`, qui fabrique le texte destiné au modèle, et la séparation n'est pas
cosmétique : c'est ici, et ici seulement, que les libellés officiels d'un opérateur
licencié entrent. Un libellé qui remonterait dans un prompt ferait dépendre les chiffres
du dépôt d'un fichier que le dépôt n'a pas le droit de distribuer (ADR-0002), et deux
opérateurs cesseraient de mesurer la même chose.

`rendu` n'importe rien d'ici, et ce module n'est importé ni par `corpus` ni par
`detection`. La règle est ainsi lisible dans le graphe des imports, pas seulement dans
une consigne.
"""

from typing import assert_never

from minerva.domaine import Fiche, Propriete
from minerva.libelles import Libelles
from minerva.registre import EntreeDuRegistre, RegistreDItems

_RETRAIT = "     "

_NON_APPLICABLE = "non-applicable"
_INTACTE = "ni sollicité ni renseigné"
"""L'oubli, dit en toutes lettres : c'est un résultat, pas un blanc dans la page."""


def _terme(propriete: Propriete) -> str:
    """Le terme de CONTEXT.md en regard de la valeur de sérialisation.

    Les valeurs d'énumération voyagent dans du JSON et des prompts, d'où l'absence
    d'accents ; un humain, lui, lit le glossaire. Le `match` est exhaustif et clos par
    `assert_never` : une propriété nouvelle fait échouer le typage plutôt que de
    s'afficher sous son nom de transport, ce qu'une table indexée n'aurait signalé qu'à
    l'exécution, et seulement sur le cas rencontré.
    """
    match propriete:
        case Propriete.SOLLICITE:
            return "sollicité"
        case Propriete.RENSEIGNE:
            return "renseigné"
    assert_never(propriete)


def _formulation_de(entree: EntreeDuRegistre, libelles: Libelles) -> str:
    """Ce qu'on écrit sous l'identifiant : le libellé officiel, sinon le construct.

    Le repli est le construct reconstruit : c'est lui que MINERVA mesure réellement, et
    il reste la description la plus honnête de l'entrée quand personne n'a de licence.

    Prend l'entrée et non son identifiant : le Registre sait déjà rendre ses entrées, et
    les rechercher ici aurait redonné un parcours qu'il écrit trois fois — avec, en prime,
    une branche « entrée introuvable » que rien ne peut atteindre.
    """
    officiel = libelles.pour(entree.identifiant)
    return f"« {officiel} »" if officiel is not None else entree.construct_sonde


def decrire_fiche(fiche: Fiche, registre: RegistreDItems, libelles: Libelles) -> str:
    """La Fiche telle qu'un humain doit la lire, entrée par entrée dans l'ordre du Registre.

    Les libellés sont exigés à l'appel, sans valeur par défaut : `Libelles.absentes()` dit
    qu'on n'en a pas, et le dire vaut mieux que de l'obtenir par omission — c'est la
    différence entre un affichage sans licence et un fichier qu'on croyait avoir chargé.
    """
    non_applicables = registre.non_applicables(fiche.polarites())
    verdicts = fiche.par_identifiant()
    lignes: list[str] = []

    for entree in registre.entrees():
        identifiant = entree.identifiant
        verdict = verdicts.get(identifiant)
        etats = [
            _terme(propriete)
            for propriete in Propriete
            if verdict is not None and verdict.porte(propriete)
        ]
        if identifiant in non_applicables:
            etats.append(_NON_APPLICABLE)

        lignes.append(f"{identifiant} — {' · '.join(etats) or _INTACTE}")
        lignes.append(f"{_RETRAIT}{_formulation_de(entree, libelles)}")
        for empan in verdict.empans if verdict is not None else []:
            locuteur = empan.role.locuteur.value
            lignes.append(f"{_RETRAIT}[{empan.indice_tour}] {locuteur} : « {empan.passage} »")

    return "\n".join(lignes)
