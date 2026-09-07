# Périmètre non-diagnostique

MINERVA mesure la conduite d'un entretien, jamais l'état du patient. Pour chaque item il produit deux verdicts — sollicité, renseigné — et leurs empans de preuve, et il ne calcule ni la cotation MINI des items, ni le diagnostic qui en découlerait.

La raison est réglementaire autant que scientifique. Le MINI est construit pour qu'un profil coté se traduise mécaniquement en diagnostic : stocker la cotation par item mettrait MINERVA à une agrégation près d'un outil diagnostique. Dès qu'une sortie oriente la conduite clinique auprès d'un patient réel ou produit un profil symptomatique, l'outil entre dans le champ du dispositif médical (règlement UE 2017/745, vraisemblablement classe IIa par la règle 11), avec le coût de conformité correspondant.

## Conséquences

- Un item renseigné est conservé sous forme d'empans de preuve, pas de valeur cotée.
- Une exception étroite a été ouverte depuis, pour les seuls Items filtres du graphe de saut : voir [ADR-0006](./0006-polarite-des-items-filtres.md). Elle ne porte que sur le branchement de l'entretien, et le périmètre non-diagnostique tient.
- L'usage recherche et audit rétrospectif est dans le périmètre. Un feedback pédagogique différé au clinicien y reste. Une assistance à l'entretien en temps réel, ou toute cotation, n'y sont pas.
