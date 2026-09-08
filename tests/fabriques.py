"""Fabriques partagées par les tests.

Ne contient que ce qui est vraiment commun. Les Registres eux-mêmes restent locaux à
chaque fichier : ils diffèrent pour de bonnes raisons, et les fondre obligerait à tordre
les assertions qui en dépendent.
"""

from minerva.registre import Item, Porte, Provenance


def provenances_de_test(identifiant: str) -> tuple[Provenance, ...]:
    """Deux lectures fictives, juste de quoi satisfaire ADR-0003.

    Les tests de mécanique n'ont aucun intérêt clinique : ce qui compte est que la
    contrainte de double provenance s'applique à eux comme au reste, sans qu'ils aient à
    inventer une bibliographie.
    """
    return (
        Provenance(source="fabrique de test A", construct_lu=f"lecture A de {identifiant}"),
        Provenance(source="fabrique de test B", construct_lu=f"lecture B de {identifiant}"),
    )


def item(identifiant: str, module: str = "A", porte: Porte | None = None) -> Item:
    """Un Item de test, sans intérêt clinique : seuls comptent son identifiant et sa porte."""
    return Item(
        identifiant=identifiant,
        module=module,
        construct_sonde=f"construct de {identifiant}",
        provenances=provenances_de_test(identifiant),
        porte=porte,
    )
