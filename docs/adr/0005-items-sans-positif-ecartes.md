# Un Item sans aucun positif est écarté de la macro-moyenne

Le F1 d'un Item se calcule sur l'ensemble du corpus, puis se moyenne sur les Items. Un Item que la référence ne porte jamais et que la détection ne prédit jamais n'a aucun positif : sa précision et son rappel sont indéfinis. Nous l'**écartons de la moyenne** plutôt que de le compter zéro, et l'exclusion vaut propriété par propriété — un Item peut être mesurable sur `Sollicité` et écarté sur `Renseigné`.

La convention usuelle des bibliothèques de métriques est de rendre zéro dans ce cas. Elle est inadaptée ici : dans un Entretien donné, la plupart des Items d'un Module ne sont légitimement pas touchés, et la macro-moyenne serait dominée par des Items que personne ne pouvait réussir. Écarter dit « non mesurable sur ce corpus » là où zéro dirait « raté », ce qui est faux.

## Conséquences

- Le dénominateur de la macro-moyenne varie avec le corpus. Deux exécutions sur des corpus différents ne sont pas directement comparables, et un chiffre publié sans son dénominateur ne veut rien dire.
- `items_ecartes` est rapporté à côté de chaque moyenne, et le F1 de chaque Item mesurable est exposé sous elle : le dénominateur est toujours lisible, jamais implicite.
- Un corpus qui n'exerce jamais un Item ne dit rien de cet Item. C'est un défaut de conception du corpus, que l'exclusion rend visible au lieu de le masquer derrière un zéro — et c'est ce que les Phénomènes adverses de la Spécification doivent corriger.
