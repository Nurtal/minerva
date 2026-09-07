# Le corpus est partitionné par modèle générateur

Le corpus synthétique est découpé en partitions, une par modèle générateur, et **aucun modèle n'est évalué en détection sur la partition qu'il a produite**. Une partition neutre, générée par un modèle absent de l'ensemble des détecteurs, sert de référence propre.

MINERVA fait générer ses entretiens par des LLM et détecter par des LLM. Sans cette règle, un modèle serait évalué sur des textes portant ses propres régularités : on mesurerait une auto-cohérence en croyant mesurer une exactitude. La contrainte doit être posée dans la structure du corpus dès la génération ; elle ne se rattrape pas au moment de l'analyse.

## Conséquences

- Les scores intra-famille et croisés sont rapportés tous les deux : leur écart mesure le biais de génération et devient un résultat plutôt qu'un angle mort.
- Toute performance sur corpus synthétique est un plafond, jamais une performance attendue sur entretien réel.
