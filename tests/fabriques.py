"""Fabriques partagées par les tests.

Ne contient que ce qui est vraiment commun. Les Registres eux-mêmes restent locaux à
chaque fichier : ils diffèrent pour de bonnes raisons, et les fondre obligerait à tordre
les assertions qui en dépendent.
"""

from minerva.registre import Item, Porte


def item(identifiant: str, module: str = "A", porte: Porte | None = None) -> Item:
    """Un Item de test, sans intérêt clinique : seuls comptent son identifiant et sa porte."""
    return Item(
        identifiant=identifiant,
        module=module,
        construct_sonde=f"construct de {identifiant}",
        source="fabrique de test",
        porte=porte,
    )
