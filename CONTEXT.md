# MINERVA

MINERVA mesure la couverture du MINI (Mini International Neuropsychiatric Interview) à partir de la retranscription d'un entretien psychiatrique. Le programme prend en entrée le texte de l'entretien et détermine, item par item, ce que le clinicien a sollicité et ce qu'il a renseigné.

## Langage

### Entretien

**Entretien** :
Une rencontre clinique entre un clinicien et un patient, dont MINERVA analyse la trace écrite.
_Éviter_ : consultation, séance, session

**Retranscription** :
Le texte intégral d'un entretien, découpé en tours de parole attribués. Unique entrée de MINERVA.
_Éviter_ : transcript, verbatim, transcription

**Tour de parole** :
Une prise de parole continue d'un locuteur, portant son locuteur et son texte. Unité de base d'une retranscription.
_Éviter_ : réplique, énoncé, intervention, turn

**Clinicien** :
Le locuteur qui conduit l'entretien. Seul locuteur dont un tour de parole peut solliciter un item.
_Éviter_ : praticien, médecin, thérapeute, évaluateur

**Patient** :
Le locuteur interrogé. Ses tours de parole renseignent des items mais n'en sollicitent aucun.
_Éviter_ : sujet, participant, interviewé

### Instrument

**MINI** :
L'entretien diagnostique structuré dont MINERVA mesure la couverture. Version de référence du projet : MINI 7.0.2 (aligné DSM-5), en français.
_Éviter_ : questionnaire, échelle, test

**Module** :
Une section du MINI portant sur un trouble ou un domaine clinique, désignée par un identifiant court (A, B, … MB, N…). Regroupe des items et porte sa propre logique de filtre.
_Éviter_ : section, catégorie, domaine

**Item** :
Une question numérotée du MINI (A1, A2a, A3b…). Unité de mesure de MINERVA : c'est de l'item qu'on dit s'il est sollicité, renseigné ou non-applicable.
_Éviter_ : question, critère, symptôme

**Qualificatif** :
Une entrée du registre de portée module — cadre temporel, fréquence — dont les items du module héritent. Se sollicite et se renseigne comme un item, sans correspondre à une question du MINI.
_Éviter_ : critère temporel, contrainte, modificateur

**Porte** :
Une condition du registre qui décide si un item est attendu : au moins tant d'opérandes vrais parmi un ensemble d'items filtres et de sous-portes. En tête de module, elle écarte tout le module ; en cours de module, elle n'écarte que ce qu'elle garde.
_Éviter_ : filtre, condition, garde, saut

**Polarité** :
La réponse à un item filtre — positive, négative, ou indéterminée. Seuls les items qu'une porte référence en portent une. C'est un fait de branchement de l'entretien, jamais une cotation.
_Éviter_ : valeur, cotation, score, réponse

**Registre d'items** :
La description structurée des items du MINI utilisée par MINERVA — identifiant stable, module, construct sondé, qualificatifs requis, relations de filtre. Ne contient pas le libellé officiel des items, qui reste hors du dépôt.
_Éviter_ : référentiel, base d'items, grille

### Corpus

**Spécification** :
Le tirage qui décrit un entretien avant qu'il n'existe : pour chaque item, l'état visé, plus les cas difficiles à réaliser. Fait office de vérité terrain, vraie par construction.
_Éviter_ : scénario, cas de test, gold, annotation

**Phénomène adverse** :
Une difficulté que la spécification impose de réaliser dans l'entretien, rattachée à l'item qu'elle vise — question laissée sans réponse, apport spontané, faux ami, négation, module légitimement sauté.
_Éviter_ : cas limite, edge case, piège, cas dur

**Corpus synthétique** :
L'ensemble des entretiens générés à partir de spécifications. Unique base d'évaluation de MINERVA.
_Éviter_ : jeu de données, dataset, échantillon

### Mesure

**Sollicité** :
Propriété d'un item dont le contenu a été demandé par un tour de parole du clinicien. Porte sur ce que fait le clinicien, indépendamment de la réponse obtenue.
_Éviter_ : posé, demandé, abordé, exploré

**Renseigné** :
Propriété d'un item pour lequel l'entretien fournit de quoi le coter selon les critères du MINI. Un item peut être renseigné sans avoir été sollicité, lorsque le patient en apporte spontanément le contenu.
_Éviter_ : récupéré, obtenu, couvert, rempli, complété

**Non-applicable** :
Propriété d'un item dont une porte est établie et négative. Un item non-applicable n'est pas un oubli. Une porte indéterminée n'écarte rien : ne pas avoir demandé n'excuse pas.
_Éviter_ : sauté, ignoré, hors périmètre, N/A

**Fiche** :
L'ensemble des verdicts d'un Entretien, un par Item du Registre. La Spécification en porte une et la détection en rend une : c'est le même type des deux côtés, ce qui fait de l'évaluation un diff.
_Éviter_ : rapport, résultat, sortie, grille

**Empan de preuve** :
Un passage exact de la retranscription établissant qu'un item est sollicité, ou qu'il est renseigné, conservé avec sa position et le rôle qu'il joue. Un item porte plusieurs empans, un empan peut servir plusieurs items. Seule forme sous laquelle MINERVA conserve le contenu d'un item.
_Éviter_ : citation, extrait, span, justification
