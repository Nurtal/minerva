# Les Items filtres, et eux seuls, portent une polarité

Un Item qui sert de porte au graphe de saut porte un booléen `positif` : la réponse était-elle positive ou négative. Aucun autre Item n'en porte, et la polarité d'un Item filtre non établi reste indéterminée. L'ensemble concerné est calculé par le Registre lui-même — ce sont exactement les Items qu'une porte référence, jamais un de plus.

C'est une exception à [ADR-0001](./0001-perimetre-non-diagnostique.md), et elle était inévitable. Dans le MINI, un Module est sauté quand sa question filtre est cotée **non** ; la porte s'évalue sur la valeur de l'Item, pas sur le fait qu'il soit Renseigné. Sans polarité, la seule dérivation possible est « la porte n'est pas Renseignée », ce qui produit une mesure absurde : un Entretien qui ne demande rien laisse tous ses filtres non renseignés, tout devient Non-applicable, et le dénominateur s'effondre. La mesure récompenserait alors le fait de ne rien demander, ce que le projet a explicitement écarté dès sa conception.

## Ce que l'exception ne remet pas en cause

- Les Items de symptôme ne sont pas cotés. Un Item Renseigné reste conservé sous forme d'Empans de preuve, jamais de valeur.
- MINERVA ne produit ni profil symptomatique ni diagnostic. Un bit par filtre décrit le **branchement de l'entretien**, pas l'état du patient : il dit quel chemin le Clinicien était en droit de suivre.
- Le périmètre non-diagnostique d'ADR-0001 tient : il n'existe aucune agrégation des polarités vers un diagnostic, et le Registre n'expose aucun moyen d'en construire une.

## Conséquences

- Une porte indéterminée n'écarte jamais rien. Un Item n'est Non-applicable que si sa porte est **établie et négative** — c'est ce qui neutralise l'incitation perverse, et c'est vérifié exhaustivement.
- La détection doit rendre la polarité des Items filtres. Toute polarité offerte pour un Item non filtre est jetée à la frontière : la portée de l'exception est appliquée par le code, pas seulement documentée.
- Le graphe se déroule deux fois, sur les polarités prédites puis sur celles de référence. L'écart mesure l'erreur de propagation — un seul filtre mal détecté fait tomber un Module entier — et l'isole de l'erreur de détection.
