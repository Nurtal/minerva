"""La règle de non-contamination, posée dans la structure du Corpus.

Sans elle, un modèle serait évalué sur des Entretiens qu'il a lui-même écrits, où il
retrouverait ses propres régularités : on mesurerait une auto-cohérence en croyant
mesurer une exactitude. La contrainte se pose à la génération, elle ne se rattrape pas
au moment de l'analyse.
"""

import pytest
from pydantic import ValidationError

from minerva.corpus import Specification, generer
from minerva.domaine import (
    CorpusSynthetique,
    EmpanDePreuve,
    Entretien,
    Fiche,
    IdentiteModele,
    Locuteur,
    Retranscription,
    RoleEmpan,
    Style,
    TourDeParole,
    VerdictItem,
)
from minerva.evaluation import Contamination, EntretienEvalue, evaluer_par_provenance
from minerva.modele import AdaptateurFactice
from minerva.registre import RegistreDItems, registre_module_a_reduit
from tests.fabriques import item


def registre_plat(*identifiants: str) -> RegistreDItems:
    return RegistreDItems(items=[item(ident) for ident in identifiants])


TOUT_ETEINT = {
    "A1": (False, False),
    "A2": (False, False),
    "A3a": (False, False),
    "A_cadre": (False, False),
}

CLAUDE = IdentiteModele(nom="claude-opus-5", famille="anthropic")
AUTRE_CLAUDE = IdentiteModele(nom="claude-haiku-4-5", famille="anthropic")
MISTRAL = IdentiteModele(nom="mistral-large", famille="mistral")


def specification_eteinte() -> Specification:
    return Specification(
        fiche_visee=Fiche(
            verdicts=[
                VerdictItem(identifiant=ident, sollicite=sol, renseigne=ren, empans=[])
                for ident, (sol, ren) in TOUT_ETEINT.items()
            ]
        )
    )


def entretien_vide() -> Entretien:
    return Entretien(
        retranscription=Retranscription(
            tours=[
                TourDeParole(indice=0, locuteur=Locuteur.CLINICIEN, texte="Bonjour."),
                TourDeParole(indice=1, locuteur=Locuteur.PATIENT, texte="Bonjour."),
            ]
        ),
        reference=Fiche(
            verdicts=[
                VerdictItem(identifiant=ident, sollicite=False, renseigne=False, empans=[])
                for ident in TOUT_ETEINT
            ]
        ),
    )


def test_un_entretien_sait_de_quel_generateur_il_vient() -> None:
    """Le rattachement se fait à la génération, pas après coup.

    Demander au lecteur de se souvenir quel modèle a écrit quoi serait une erreur
    silencieuse, et c'est exactement ce que la règle doit rendre impossible.
    """
    entretien = generer(
        specification_eteinte(),
        registre_module_a_reduit(),
        AdaptateurFactice([entretien_vide()], identite=MISTRAL),
    )

    assert entretien.generateur == MISTRAL


def test_l_identite_du_generateur_n_est_pas_fournie_par_l_appelant() -> None:
    """C'est le modèle qui dit qui il est ; un nom passé par l'appelant s'étiquette de travers."""
    adaptateur = AdaptateurFactice([entretien_vide()], identite=CLAUDE)

    assert adaptateur.identite == CLAUDE
    assert (
        generer(specification_eteinte(), registre_module_a_reduit(), adaptateur).generateur
        == CLAUDE
    )


def entretien_de(generateur: IdentiteModele) -> Entretien:
    return entretien_vide().model_copy(update={"generateur": generateur})


def test_le_corpus_se_decoupe_en_une_partition_par_generateur() -> None:
    corpus = CorpusSynthetique(
        entretiens=[entretien_de(CLAUDE), entretien_de(MISTRAL), entretien_de(CLAUDE)]
    )

    assert {nom: len(part) for nom, part in corpus.partitions().items()} == {
        "claude-opus-5": 2,
        "mistral-large": 1,
    }


def test_un_entretien_de_provenance_inconnue_n_a_pas_sa_place_dans_un_corpus() -> None:
    """Il serait impossible de dire s'il contamine un détecteur ou non.

    Le laisser entrer reviendrait à faire reposer la règle sur la vigilance du lecteur,
    ce qu'elle existe précisément pour éviter.
    """
    with pytest.raises(ValidationError):
        CorpusSynthetique(entretiens=[entretien_vide()])


def test_un_frere_de_famille_n_est_pas_une_reference_propre() -> None:
    """La référence propre s'entend au niveau de la famille, pas du nom.

    Un modèle absent du panel mais frère d'un détecteur partage ses régularités : le
    prendre pour référence propre reviendrait à mesurer le biais avec le biais.
    """
    corpus = CorpusSynthetique(
        entretiens=[entretien_de(CLAUDE), entretien_de(MISTRAL), entretien_de(AUTRE_CLAUDE)]
    )

    neutre = corpus.partition_neutre([CLAUDE])

    assert [entretien.generateur for entretien in neutre] == [MISTRAL]


def test_un_corpus_sans_partition_neutre_le_dit() -> None:
    """Un corpus dont chaque partition est parente d'un détecteur n'a aucune référence propre.

    Le silence donnerait un benchmark qu'on croit propre alors qu'il ne l'est pas.
    """
    corpus = CorpusSynthetique(entretiens=[entretien_de(CLAUDE), entretien_de(MISTRAL)])

    assert corpus.partition_neutre([CLAUDE, MISTRAL]) == []


def fiche(**etats: tuple[bool, bool]) -> Fiche:
    return Fiche(
        verdicts=[
            VerdictItem(
                identifiant=ident,
                sollicite=sol,
                renseigne=ren,
                empans=[EmpanDePreuve(indice_tour=0, role=RoleEmpan.RENSEIGNEMENT, passage="p")]
                if ren
                else [],
            )
            for ident, (sol, ren) in etats.items()
        ]
    )


def evalue(generateur: IdentiteModele, prediction: Fiche) -> EntretienEvalue:
    return EntretienEvalue(
        style=Style(),
        reference=fiche(A1=(True, True)),
        prediction=prediction,
        generateur=generateur,
    )


def test_un_modele_ne_peut_pas_etre_evalue_sur_ce_qu_il_a_ecrit() -> None:
    """Le refus est le cœur de la règle : sinon on mesure une auto-cohérence."""
    with pytest.raises(Contamination, match="claude-opus-5"):
        evaluer_par_provenance(
            CLAUDE,
            [CLAUDE, MISTRAL],
            [evalue(CLAUDE, fiche(A1=(True, True)))],
            registre_plat("A1"),
        )


def test_l_ecart_entre_intra_famille_et_croise_mesure_le_biais_de_generation() -> None:
    """Le détecteur réussit sur ce qu'un frère de sa famille a écrit, échoue ailleurs.

    C'est exactement le biais que la règle existe pour rendre visible : sans la
    ventilation, un score moyen de moitié ne dirait pas d'où vient la moitié perdue.
    """
    scores = evaluer_par_provenance(
        CLAUDE,
        [CLAUDE, MISTRAL],
        [
            evalue(AUTRE_CLAUDE, fiche(A1=(True, True))),
            evalue(MISTRAL, fiche(A1=(False, False))),
        ],
        registre_plat("A1"),
    )

    assert scores.intra_famille is not None
    assert scores.croise is not None
    assert scores.intra_famille.renseigne.rappel == 1.0
    assert scores.croise.renseigne.rappel == 0.0
    assert scores.ecart_rappel_renseigne == 1.0


def test_sans_partition_croisee_l_ecart_n_est_pas_calculable() -> None:
    """Un écart incalculable vaut mieux qu'un zéro, qui se lirait comme « pas de biais »."""
    scores = evaluer_par_provenance(
        CLAUDE, [CLAUDE], [evalue(AUTRE_CLAUDE, fiche(A1=(True, True)))], registre_plat("A1")
    )

    assert scores.croise is None
    assert scores.ecart_rappel_renseigne is None


def test_une_partition_etrangere_au_panel_est_la_seule_reference_propre() -> None:
    """Trois provenances, pas deux : la neutre ne doit pas se confondre avec le croisé.

    Un générateur d'une autre famille du panel partage tout de même le monde des
    détecteurs ; un générateur étranger au panel est le seul dont on puisse dire qu'aucun
    détecteur ne lui doit quoi que ce soit.
    """
    ETRANGER = IdentiteModele(nom="qwen-3", famille="qwen")

    scores = evaluer_par_provenance(
        CLAUDE,
        [CLAUDE, MISTRAL],
        [
            evalue(AUTRE_CLAUDE, fiche(A1=(True, True))),
            evalue(MISTRAL, fiche(A1=(True, True))),
            evalue(ETRANGER, fiche(A1=(True, True))),
        ],
        registre_plat("A1"),
    )

    assert scores.intra_famille is not None
    assert scores.croise is not None
    assert scores.neutre is not None


def test_un_nom_epingle_ou_de_casse_differente_ne_franchit_pas_la_garde() -> None:
    """La garde se trompe du côté sûr : deux noms qui se recouvrent sont le même modèle.

    « claude-opus-5 » et « claude-opus-5-20250101 » désignent le même modèle épinglé
    autrement, et la casse ne doit jamais décider d'une contamination.
    """
    epingle = IdentiteModele(nom="Claude-Opus-5-20250101", famille="Anthropic")

    with pytest.raises(Contamination):
        evaluer_par_provenance(
            CLAUDE, [CLAUDE], [evalue(epingle, fiche(A1=(True, True)))], registre_plat("A1")
        )


def test_un_entretien_non_issu_de_la_generation_est_refuse_a_l_appariement() -> None:
    """La provenance inconnue est refusée là où elle se voit, pas perdue au moment d'analyser.

    C'est ce que veut dire « la contrainte ne se rattrape pas au moment de l'analyse » :
    le refus doit tomber quand on apparie, pas se dissoudre en un entretien silencieusement
    ignoré dans les chiffres.
    """
    with pytest.raises(Contamination, match="provenance inconnue"):
        EntretienEvalue.depuis(entretien_vide(), fiche(A1=(True, True)))


def test_l_appariement_fait_suivre_le_style_et_le_generateur() -> None:
    """Le pont entre un Entretien généré et son évaluation ne se fait pas à la main."""
    entretien = generer(
        specification_eteinte(),
        registre_module_a_reduit(),
        AdaptateurFactice([entretien_vide()], identite=MISTRAL),
    )

    apparie = EntretienEvalue.depuis(entretien, fiche(A1=(True, True)))

    assert apparie.generateur == MISTRAL
    assert apparie.style == entretien.style
