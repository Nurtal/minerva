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

from minerva.domaine import Fiche, Propriete
from minerva.libelles import Libelles
from minerva.registre import RegistreDItems

_RETRAIT = "     "

_TERME = {
    Propriete.SOLLICITE: "sollicité",
    Propriete.RENSEIGNE: "renseigné",
}
"""Les termes de CONTEXT.md, en regard des valeurs de sérialisation.

Les valeurs d'énumération voyagent dans du JSON et des prompts, d'où l'absence
d'accents ; un humain, lui, lit le glossaire. La table est totale sur `Propriete`, donc
une propriété nouvelle ne peut pas s'afficher sous son nom de transport sans qu'on ait
choisi comment la dire."""

_NON_APPLICABLE = "non-applicable"
_INTACTE = "ni sollicité ni renseigné"
"""L'oubli, dit en toutes lettres : c'est un résultat, pas un blanc dans la page."""


def _enonce(identifiant: str, registre: RegistreDItems, libelles: Libelles) -> str:
    """Ce qu'on écrit sous l'identifiant : le libellé officiel, sinon le construct.

    Le repli est le construct reconstruit et non l'identifiant nu : c'est lui que MINERVA
    mesure réellement, et il reste la description la plus honnête de l'entrée quand
    personne n'a de licence.
    """
    officiel = libelles.pour(identifiant)
    if officiel is not None:
        return f"« {officiel} »"
    for entree in (*registre.items, *registre.qualificatifs):
        if entree.identifiant == identifiant:
            return entree.construct_sonde
    return identifiant


def decrire_fiche(fiche: Fiche, registre: RegistreDItems, libelles: Libelles) -> str:
    """La Fiche telle qu'un humain doit la lire, entrée par entrée dans l'ordre du Registre.

    Les libellés sont exigés à l'appel, sans valeur par défaut : `Libelles.absentes()` dit
    qu'on n'en a pas, et le dire vaut mieux que de l'obtenir par omission — c'est la
    différence entre un affichage sans licence et un fichier qu'on croyait avoir chargé.
    """
    non_applicables = registre.non_applicables(fiche.polarites())
    verdicts = fiche.par_identifiant()
    lignes: list[str] = []

    for identifiant in registre.identifiants():
        verdict = verdicts.get(identifiant)
        etats = [
            _TERME[propriete]
            for propriete in Propriete
            if verdict is not None and verdict.porte(propriete)
        ]
        if identifiant in non_applicables:
            etats.append(_NON_APPLICABLE)

        lignes.append(f"{identifiant} — {' · '.join(etats) or _INTACTE}")
        lignes.append(f"{_RETRAIT}{_enonce(identifiant, registre, libelles)}")
        for empan in verdict.empans if verdict is not None else []:
            locuteur = empan.role.locuteur.value
            lignes.append(f"{_RETRAIT}[{empan.indice_tour}] {locuteur} : « {empan.passage} »")

    return "\n".join(lignes)
