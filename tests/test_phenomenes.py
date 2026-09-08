"""Les Phénomènes adverses : les difficultés que la Spécification impose de réaliser.

Sans eux le Corpus n'éprouve que le cas moyen — un Patient coopératif et explicite — et
une baisse de résultat reste ininterprétable. Chacun vise une entrée précise du Registre,
et quatre des cinq impliquent définitionnellement un état : les déclarer sans commander
l'état correspondant serait une Spécification qui se contredit.
"""

import pytest

from minerva.corpus import (
    ModuleSaute,
    NaturePhenomene,
    PhenomeneAdverse,
    PhenomeneSurEntree,
    Specification,
    SpecificationIncoherente,
    generer,
)
from minerva.domaine import (
    AxeDeStyle,
    Cooperation,
    Directivite,
    EmpanDePreuve,
    Entretien,
    Fiche,
    IdentiteModele,
    Locuteur,
    Loquacite,
    Retranscription,
    RoleEmpan,
    Style,
    TourDeParole,
    VerdictItem,
)
from minerva.evaluation import EntretienEvalue, evaluer, evaluer_par_axe
from minerva.modele import AdaptateurFactice, ReponseIncoherente
from minerva.registre import RegistreDItems, registre_module_a_reduit
from tests.fabriques import item


def registre_plat(*identifiants: str) -> RegistreDItems:
    return RegistreDItems(items=[item(ident) for ident in identifiants])


GENERATEUR = IdentiteModele(nom="factice", famille="factice")

TOUT_ETEINT = {
    "A1": (False, False),
    "A2": (False, False),
    "A3a": (False, False),
    "A_cadre": (False, False),
}


def specification(
    etats: dict[str, tuple[bool, bool]],
    phenomenes: list[PhenomeneAdverse] | None = None,
    polarites: dict[str, bool] | None = None,
    style: Style | None = None,
) -> Specification:
    polarites = polarites or {}
    return Specification(
        fiche_visee=Fiche(
            verdicts=[
                VerdictItem(
                    identifiant=ident,
                    sollicite=sol,
                    renseigne=ren,
                    positif=polarites.get(ident),
                    empans=[],
                )
                for ident, (sol, ren) in etats.items()
            ]
        ),
        phenomenes=phenomenes or [],
        **({"style": style} if style else {}),
    )


def generer_avec(specification: Specification) -> None:
    generer(specification, registre_module_a_reduit(), AdaptateurFactice([]))


def test_sans_reponse_exige_un_item_sollicite_et_non_renseigne() -> None:
    """La question posée qui n'obtient rien : c'est exactement cet état, pas un autre."""
    contradictoire = specification(
        TOUT_ETEINT | {"A1": (True, True)},
        [PhenomeneSurEntree(nature=NaturePhenomene.SANS_REPONSE, cible="A1")],
    )

    with pytest.raises(SpecificationIncoherente, match="sans_reponse"):
        generer_avec(contradictoire)


def test_apport_spontane_exige_un_item_renseigne_sans_avoir_ete_sollicite() -> None:
    """Ce que le Patient offre de lui-même — l'inverse exact de la question sans réponse."""
    contradictoire = specification(
        TOUT_ETEINT | {"A1": (True, True)},
        [PhenomeneSurEntree(nature=NaturePhenomene.APPORT_SPONTANE, cible="A1")],
    )

    with pytest.raises(SpecificationIncoherente, match="apport_spontane"):
        generer_avec(contradictoire)


def test_un_faux_ami_peut_coexister_avec_l_item_reellement_renseigne() -> None:
    """Le cas le plus discriminant, et il ne doit pas être interdit.

    Un contenu trompeur qui ressemble à l'item, plus l'item réellement renseigné ailleurs :
    la question devient « le détecteur ancre-t-il son verdict sur le bon passage ? ».
    Exiger l'item non renseigné supprimerait ce cas, et le priverait de tout positif — ce
    qui l'écarterait de la macro-moyenne au lieu de l'éprouver.
    """
    demande = specification(
        TOUT_ETEINT | {"A3a": (True, True)},
        [PhenomeneSurEntree(nature=NaturePhenomene.FAUX_AMI, cible="A3a")],
    )

    with pytest.raises(ReponseIncoherente, match="scénario épuisé"):
        generer_avec(demande)


def test_negation_sur_un_filtre_impose_une_polarite_negative() -> None:
    """« La réponse est explicitement négative » et « le filtre est positif » ne tiennent
    pas ensemble : sur un Item filtre, la négation *est* une polarité négative."""
    contradictoire = specification(
        TOUT_ETEINT | {"A1": (True, True)},
        [PhenomeneSurEntree(nature=NaturePhenomene.NEGATION, cible="A1")],
        polarites={"A1": True},
    )

    with pytest.raises(SpecificationIncoherente, match="negation"):
        generer_avec(contradictoire)


def test_une_polarite_commandee_exige_une_entree_renseignee() -> None:
    """On n'établit pas une réponse qu'on n'a pas.

    Sans ce contrôle, une Spécification pouvait fermer un Module sur un filtre que
    l'Entretien n'établit jamais — fabriquant comme vérité terrain l'incitation même que
    l'ADR-0006 interdit.
    """
    contradictoire = specification(TOUT_ETEINT, polarites={"A1": False})

    with pytest.raises(SpecificationIncoherente, match="non renseignée"):
        generer_avec(contradictoire)


def test_module_saute_exige_que_la_porte_du_module_soit_negative() -> None:
    """Un Module n'est pas sauté par décret : il l'est parce que son filtre est négatif."""
    contradictoire = specification(
        TOUT_ETEINT | {"A1": (True, True)},
        [ModuleSaute(module="A")],
        polarites={"A1": True},
    )

    with pytest.raises(SpecificationIncoherente, match="module_saute"):
        generer_avec(contradictoire)


def test_un_phenomene_visant_une_entree_inconnue_est_refuse() -> None:
    """Une difficulté qui ne vise rien ne sera jamais réalisée ni mesurée."""
    with pytest.raises(SpecificationIncoherente, match="Z9"):
        generer_avec(
            specification(
                TOUT_ETEINT, [PhenomeneSurEntree(nature=NaturePhenomene.NEGATION, cible="Z9")]
            )
        )


def test_les_phenomenes_et_le_style_traversent_la_couture() -> None:
    """Ce que la Spécification impose doit atteindre le modèle, sinon rien ne le réalise.

    Le prompt est ce qui traverse le port modèle : c'est le comportement observable de
    `corpus` à sa couture, pas un détail interne.
    """
    adaptateur = AdaptateurFactice([])
    demande = specification(
        TOUT_ETEINT | {"A1": (True, False)},
        [PhenomeneSurEntree(nature=NaturePhenomene.SANS_REPONSE, cible="A1")],
        style=Style(
            loquacite=Loquacite.LACONIQUE,
            cooperation=Cooperation.EVITANTE,
            directivite=Directivite.LIBRE,
        ),
    )

    with pytest.raises(ReponseIncoherente, match="scénario épuisé"):
        generer(demande, registre_module_a_reduit(), adaptateur)

    prompt = adaptateur.prompts[0]
    assert "sans_reponse" in prompt
    assert "A1" in prompt
    assert "laconique" in prompt
    assert "evitante" in prompt
    assert "libre" in prompt


def test_le_style_est_fixe_par_la_specification_et_non_tire_au_hasard() -> None:
    """Deux générations de la même Spécification demandent exactement le même style.

    Sans quoi une baisse de résultat resterait ininterprétable : on ne saurait pas si le
    modèle échoue sur les Patients évasifs ou sur autre chose.
    """
    demande = specification(TOUT_ETEINT)

    prompts = []
    for _ in range(2):
        adaptateur = AdaptateurFactice([])
        with pytest.raises(ReponseIncoherente, match="scénario épuisé"):
            generer(demande, registre_module_a_reduit(), adaptateur)
        prompts.append(adaptateur.prompts[0])

    assert prompts[0] == prompts[1]


def fiche(**etats: tuple[bool, bool]) -> Fiche:
    return Fiche(
        verdicts=[
            VerdictItem(identifiant=ident, sollicite=sol, renseigne=ren, empans=[])
            for ident, (sol, ren) in etats.items()
        ]
    )


def test_les_chiffres_se_ventilent_par_axe_de_style() -> None:
    """Un axe de style contrôlé ne sert à rien si les chiffres ne s'y rapportent pas.

    Deux Entretiens, l'un avec un Patient laconique où la détection rate tout, l'autre
    avec un Patient prolixe où elle réussit. Ventilés par axe, l'écart se lit ; confondus,
    on saurait seulement que le score moyen est de moitié.
    """
    parfait = fiche(A1=(True, True))
    rate = fiche(A1=(False, False))

    cas = [
        EntretienEvalue(
            style=Style(loquacite=Loquacite.LACONIQUE),
            reference=fiche(A1=(True, True)),
            prediction=rate,
            generateur=GENERATEUR,
        ),
        EntretienEvalue(
            style=Style(loquacite=Loquacite.PROLIXE),
            reference=fiche(A1=(True, True)),
            prediction=parfait,
            generateur=GENERATEUR,
        ),
    ]

    par_axe = evaluer_par_axe(cas, registre_plat("A1"))

    assert par_axe[AxeDeStyle.LOQUACITE]["laconique"].renseigne.rappel == 0.0
    assert par_axe[AxeDeStyle.LOQUACITE]["prolixe"].renseigne.rappel == 1.0
    assert set(par_axe) == set(AxeDeStyle)


def test_un_axe_sans_variation_rend_un_seul_groupe() -> None:
    """Les deux Entretiens partagent la même directivité : rien à comparer sur cet axe."""
    cas = [
        EntretienEvalue(
            style=Style(loquacite=Loquacite.LACONIQUE),
            reference=fiche(A1=(True, True)),
            prediction=fiche(A1=(True, True)),
            generateur=GENERATEUR,
        ),
        EntretienEvalue(
            style=Style(loquacite=Loquacite.PROLIXE),
            reference=fiche(A1=(True, True)),
            prediction=fiche(A1=(True, True)),
            generateur=GENERATEUR,
        ),
    ]

    par_axe = evaluer_par_axe(cas, registre_plat("A1"))

    assert set(par_axe[AxeDeStyle.DIRECTIVITE]) == {"semi_directif"}


def test_un_module_legitimement_saute_produit_les_drapeaux_non_applicable_attendus() -> None:
    """De la difficulté commandée jusqu'aux drapeaux, en passant par la génération.

    Le Clinicien établit que ni l'humeur ni l'anhédonie ne sont là, et passe. Le reste du
    Module A est écarté à raison — son cadre temporel compris, puisqu'un Module sans objet
    n'a pas d'ancienneté à dater.
    """
    registre = registre_module_a_reduit()
    demande = specification(
        {
            "A1": (True, True),
            "A2": (True, True),
            "A3a": (False, False),
            "A_cadre": (False, False),
        },
        [ModuleSaute(module="A")],
        polarites={"A1": False, "A2": False},
    )

    ecrit = Entretien(
        retranscription=Retranscription(
            tours=[
                TourDeParole(
                    indice=0, locuteur=Locuteur.CLINICIEN, texte="Le moral, ces jours-ci ?"
                ),
                TourDeParole(indice=1, locuteur=Locuteur.PATIENT, texte="Ça va, rien à signaler."),
                TourDeParole(
                    indice=2, locuteur=Locuteur.CLINICIEN, texte="Du plaisir aux choses ?"
                ),
                TourDeParole(indice=3, locuteur=Locuteur.PATIENT, texte="Oui, comme d'habitude."),
            ]
        ),
        reference=Fiche(
            verdicts=[
                VerdictItem(
                    identifiant="A1",
                    sollicite=True,
                    renseigne=True,
                    positif=False,
                    empans=[
                        EmpanDePreuve(
                            indice_tour=0, role=RoleEmpan.SOLLICITATION, passage="Le moral"
                        ),
                        EmpanDePreuve(
                            indice_tour=1, role=RoleEmpan.RENSEIGNEMENT, passage="rien à signaler"
                        ),
                    ],
                ),
                VerdictItem(
                    identifiant="A2",
                    sollicite=True,
                    renseigne=True,
                    positif=False,
                    empans=[
                        EmpanDePreuve(
                            indice_tour=2,
                            role=RoleEmpan.SOLLICITATION,
                            passage="plaisir aux choses",
                        ),
                        EmpanDePreuve(
                            indice_tour=3, role=RoleEmpan.RENSEIGNEMENT, passage="comme d'habitude"
                        ),
                    ],
                ),
                VerdictItem(identifiant="A3a", sollicite=False, renseigne=False, empans=[]),
                VerdictItem(identifiant="A_cadre", sollicite=False, renseigne=False, empans=[]),
            ]
        ),
    )

    entretien = generer(demande, registre, AdaptateurFactice([ecrit]))

    assert registre.non_applicables(entretien.reference.polarites()) == {"A3a", "A_cadre"}

    mesures = evaluer([(entretien.reference, entretien.reference)], registre)
    assert mesures.conduite.oublis == {}
    assert mesures.conduite.questions_inutiles == {}
    assert mesures.conduite.non_cotables_faute_de_cadre == {}
