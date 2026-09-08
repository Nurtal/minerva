# Le corpus est partitionné par modèle générateur

Le corpus synthétique est découpé en partitions, une par modèle générateur, et **aucun modèle n'est évalué en détection sur la partition qu'il a produite**. Une partition neutre, générée par un modèle absent de l'ensemble des détecteurs, sert de référence propre.

MINERVA fait générer ses entretiens par des LLM et détecter par des LLM. Sans cette règle, un modèle serait évalué sur des textes portant ses propres régularités : on mesurerait une auto-cohérence en croyant mesurer une exactitude. La contrainte doit être posée dans la structure du corpus dès la génération ; elle ne se rattrape pas au moment de l'analyse.

## Conséquences

- Les scores intra-famille et croisés sont rapportés tous les deux : leur écart mesure le biais de génération et devient un résultat plutôt qu'un angle mort.
- Deux identités de modèle dont l'un des noms préfixe l'autre sont tenues pour le même modèle : « claude-opus-5 » et « claude-opus-5-20250101 » sont un modèle épinglé deux fois. La garde de contamination se trompe ainsi du côté sûr, au prix de refuser une évaluation licite entre deux modèles réellement distincts dont les noms se recouvrent — il faut alors les désambiguïser explicitement.
- La couverture du panel se lit en revanche sur la **famille**, jamais sur le nom : la largesse ci-dessus s'y retournerait, en laissant un détecteur réellement absent passer pour déclaré parce que son nom en recouvre un autre. Les deux gardes veulent des directions d'erreur opposées, donc pas la même règle.
- Toute performance sur corpus synthétique est un plafond, jamais une performance attendue sur entretien réel.
