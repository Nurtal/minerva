# MINERVA

MINERVA mesure la couverture d'un entretien psychiatrique : à partir de la retranscription d'un entretien entre un clinicien et son patient, il détermine, item par item, ce que le clinicien a **sollicité** et ce que l'entretien a **renseigné**, en citant les passages qui l'établissent.

Le vocabulaire du projet est défini dans [CONTEXT.md](./CONTEXT.md). Les décisions structurantes sont dans [docs/adr/](./docs/adr/).

## Ce que fait MINERVA

Pour chaque item du registre, MINERVA produit :

- **Sollicité** — le clinicien a demandé le contenu de l'item, indépendamment de la réponse obtenue ;
- **Renseigné** — l'entretien fournit de quoi coter l'item, que la question ait été posée ou que le patient l'ait apporté spontanément ;
- **Non-applicable** — drapeau dérivé, calculé en déroulant le graphe de saut du MINI sur les items renseignés ;
- les **empans de preuve** correspondants, typés selon qu'ils sollicitent ou renseignent.

Sollicité et renseigné sont deux propriétés indépendantes. Leur écart est le résultat intéressant : un item sollicité mais non renseigné signale une relance qui n'a pas eu lieu, un item renseigné sans avoir été sollicité signale ce que le patient a offert de lui-même.

## Ce que MINERVA ne fait pas

MINERVA ne cote pas les items, ne produit aucun profil symptomatique et ne pose aucun diagnostic — voir [ADR-0001](./docs/adr/0001-perimetre-non-diagnostique.md). Il ne fait pas non plus de diarisation : la retranscription lui arrive déjà découpée en tours de parole attribués.

## Périmètre

Ce dépôt couvre **le développement du modèle sur données synthétiques**. Le volet impliquant un clinicien, les données réelles et l'usage de l'outil relève d'un projet distinct, avec son propre cadre.

- Instrument de référence : MINI 7.0.2 (DSM-5), en français.
- Modules traités en v1 : **A** (épisode dépressif majeur) et **B** (risque suicidaire), soit 25 items numérotés et 42 questions cotées. Extension aux 17 modules dans un second temps.
- Langue de travail : français. Le registre est indépendant de la langue ; les formulations sont une ressource attachée aux items.

## Registre d'items

Le texte du MINI n'est pas dans ce dépôt et n'y sera pas ([ADR-0002](./docs/adr/0002-texte-du-mini-hors-depot.md)). Le registre est reconstruit depuis la littérature publiée, indexé sur la numérotation du MINI, chaque entrée citant sa source ([ADR-0003](./docs/adr/0003-registre-reconstruit.md)).

Un opérateur disposant d'une licence peut déposer son propre fichier de libellés et le charger à l'exécution : `minerva.libelles.charger` lit un objet JSON plat — identifiant d'entrée vers formulation officielle — et `minerva.affichage.decrire_fiche` s'en sert pour habiller les verdicts. Sans ce fichier, l'affichage se rabat sur le construct reconstruit et la chaîne rend exactement les mêmes chiffres.

Le fichier se désigne au lancement par la variable d'environnement `MINERVA_LIBELLES`, que `minerva.libelles.depuis_l_environnement` lit à chaque appel :

```sh
export MINERVA_LIBELLES=libelles_mini_7.0.2_fr.json
```

```python
from minerva.affichage import decrire_fiche
from minerva.libelles import depuis_l_environnement

print(decrire_fiche(fiche, registre, depuis_l_environnement()))
```

Variable non posée, aucune licence, la chaîne tourne : c'est le mode nominal. Variable posée mais vide, ou désignant un fichier absent, est en revanche une erreur et non un repli silencieux — sans quoi un opérateur croirait lire les formulations officielles et lirait des constructs reconstruits.

Composer ces deux lignes revient au programme appelant. Ce dépôt fournit le mécanisme et jamais le lancement : l'usage de l'outil relève d'un projet distinct, avec son propre cadre (voir [Périmètre](#périmètre)). C'est aussi la lettre d'ADR-0002, dont la conséquence est qu'un opérateur licencié *fournit* son fichier — le lancer n'appartient pas à ce dépôt.

**Nommez ce fichier `libelles_mini*.json`** — par exemple `libelles_mini_7.0.2_fr.json`. C'est le motif que `.gitignore` connaît, et le seul qui garantisse que le texte sous copyright ne parte pas dans un commit. Un fichier nommé autrement serait suivi par git, ce qui est précisément ce qu'ADR-0002 existe pour empêcher.

Ces libellés ne servent qu'à l'affichage et n'atteignent jamais le modèle : s'ils entraient dans un prompt, les chiffres du dépôt dépendraient d'un fichier que le dépôt n'a pas le droit de distribuer, et deux opérateurs cesseraient de mesurer la même chose. Le fichier n'est pas versionné.

**Conséquence à lire avant tout chiffre produit par ce dépôt** : MINERVA mesure la couverture d'un registre reconstruit aligné sur la structure du MINI, et non la couverture du MINI. Aucun expert n'a validé cette reconstruction dans le périmètre du projet.

## Données

Le corpus est **entièrement synthétique**. Il n'existe aucun corpus ouvert d'entretiens diagnostiques psychiatriques réels, dans aucune langue, et rien en français — cette voie est fermée, pas différée.

La génération part d'une **spécification** — états visés par item, phénomènes adverses à réaliser, axes de style traités en variables contrôlées — dont l'entretien est ensuite dérivé. La vérité terrain est donc vraie par construction, empans compris. Le corpus est partitionné par modèle générateur et aucun modèle n'est évalué sur ce qu'il a écrit ([ADR-0004](./docs/adr/0004-corpus-partitionne-par-generateur.md)).

## Approche

Détection par LLM, un passage par module, sortie structurée pour tous les items du module avec leurs empans. L'interface est figée — `retranscription + registre → verdicts + empans` — pour que la méthode reste interchangeable et que plusieurs modèles soient comparables à protocole constant. Le benchmark couvre au moins trois familles disjointes, dont un modèle à poids ouverts exécutable localement.

### Métriques

- F1 binaire par item sur `sollicité`, macro-moyenné sur les items ;
- F1 binaire par item sur `renseigné`, macro-moyenné — **le rappel est la métrique de tête** ;
- taux d'ancrage : proportion de verdicts positifs dont l'empan prédit recouvre l'empan de référence ;
- non-applicable évalué deux fois, sur les items renseignés prédits puis sur ceux de référence, pour isoler l'erreur de propagation du graphe de l'erreur de détection.

## Structure

| Module | Rôle |
|---|---|
| `registre` | Items, qualificatifs, provenances, graphe de saut. Aucun LLM, pur et exhaustivement testable. |
| `corpus` | Tirage des spécifications, génération des entretiens. |
| `detection` | `retranscription + registre → verdicts + empans`. |
| `evaluation` | Référence contre prédiction. La sortie de détection a la même forme que la spécification : l'évaluation est un diff. |

`corpus` et `detection` passent par un port modèle unique — un prompt et un schéma en entrée, une sortie structurée — avec un adaptateur par fournisseur.

## Socle technique

Python 3.12+, `uv`, `pytest`, `ruff`.
