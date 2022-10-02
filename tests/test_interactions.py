import prolif
import pytest
from MDAnalysis.topology.tables import vdwradii
from prolif.fingerprint import Fingerprint
from prolif.interactions import (_INTERACTIONS, Interaction, VdWContact,
                                 get_mapindex)
from rdkit import Chem, RDLogger

from . import mol2factory
from .test_base import ligand_mol

# disable rdkit warnings
lg = RDLogger.logger()
lg.setLevel(RDLogger.ERROR)


interaction_instances = {
    name: cls() for name, cls in _INTERACTIONS.items()
    if name not in ["Interaction", "_Distance"]
}


@pytest.fixture(scope="module")
def lig_mol(request):
    return getattr(mol2factory, request.param)()


@pytest.fixture(scope="module")
def prot_mol(request):
    return getattr(mol2factory, request.param)()


@pytest.fixture(scope="module")
def interaction_qmol(request):
    int_name, parameter = request.param.split(".")
    return getattr(interaction_instances[int_name], parameter)


class TestInteractions:
    @pytest.fixture(scope="class")
    def fingerprint(self):
        return Fingerprint()

    @pytest.mark.parametrize("func_name, lig_mol, prot_mol, expected", [
        ("cationic", "cation", "anion", True),
        ("cationic", "anion", "cation", False),
        ("cationic", "cation", "benzene", False),
        ("anionic", "cation", "anion", False),
        ("anionic", "anion", "cation", True),
        ("anionic", "anion", "benzene", False),
        ("cationpi", "cation", "benzene", True),
        ("cationpi", "cation_false", "benzene", False),
        ("cationpi", "benzene", "cation", False),
        ("cationpi", "cation", "cation", False),
        ("cationpi", "benzene", "benzene", False),
        ("pication", "benzene", "cation", True),
        ("pication", "benzene", "cation_false", False),
        ("pication", "cation", "benzene", False),
        ("pication", "cation", "cation", False),
        ("pication", "benzene", "benzene", False),
        ("pistacking", "benzene", "etf", True),
        ("pistacking", "etf", "benzene", True),
        ("pistacking", "ftf", "benzene", True),
        ("pistacking", "benzene", "ftf", True),
        ("facetoface", "benzene", "ftf", True),
        ("facetoface", "ftf", "benzene", True),
        ("facetoface", "benzene", "etf", False),
        ("facetoface", "etf", "benzene", False),
        ("edgetoface", "benzene", "etf", True),
        ("edgetoface", "etf", "benzene", True),
        ("edgetoface", "benzene", "ftf", False),
        ("edgetoface", "ftf", "benzene", False),
        ("hydrophobic", "benzene", "etf", True),
        ("hydrophobic", "benzene", "ftf", True),
        ("hydrophobic", "benzene", "chlorine", True),
        ("hydrophobic", "benzene", "anion", False),
        ("hydrophobic", "benzene", "cation", False),
        ("hbdonor", "hb_donor", "hb_acceptor", True),
        ("hbdonor", "hb_donor", "hb_acceptor_false", False),
        ("hbdonor", "hb_acceptor", "hb_donor", False),
        ("hbacceptor", "hb_acceptor", "hb_donor", True),
        ("hbacceptor", "hb_acceptor_false", "hb_donor", False),
        ("hbacceptor", "hb_donor", "hb_acceptor", False),
        ("xbdonor", "xb_donor", "xb_acceptor", True),
        ("xbdonor", "xb_donor", "xb_acceptor_false_xar", False),
        ("xbdonor", "xb_donor", "xb_acceptor_false_axd", False),
        ("xbdonor", "xb_acceptor", "xb_donor", False),
        ("xbacceptor", "xb_acceptor", "xb_donor", True),
        ("xbacceptor", "xb_acceptor_false_xar", "xb_donor", False),
        ("xbacceptor", "xb_acceptor_false_axd", "xb_donor", False),
        ("xbacceptor", "xb_donor", "xb_acceptor", False),
        ("metaldonor", "metal", "ligand", True),
        ("metaldonor", "metal_false", "ligand", False),
        ("metaldonor", "ligand", "metal", False),
        ("metalacceptor", "ligand", "metal", True),
        ("metalacceptor", "ligand", "metal_false", False),
        ("metalacceptor", "metal", "ligand", False),
        ("vdwcontact", "benzene", "etf", True),
        ("vdwcontact", "hb_acceptor", "metal_false", False),
    ], indirect=["lig_mol", "prot_mol"])
    def test_interaction(self, fingerprint, func_name, lig_mol, prot_mol, expected):
        interaction = getattr(fingerprint, func_name)
        assert interaction(lig_mol, prot_mol) is expected

    def test_warning_supersede(self):
        old = id(_INTERACTIONS["Hydrophobic"])
        with pytest.warns(UserWarning,
                          match="interaction has been superseded"):
            class Hydrophobic(Interaction):
                def detect(self):
                    pass
        new = id(_INTERACTIONS["Hydrophobic"])
        assert old != new
        # fix dummy Hydrophobic class being reused in later unrelated tests

        class Hydrophobic(prolif.interactions.Hydrophobic):
            __doc__ = prolif.interactions.Hydrophobic.__doc__

    def test_error_no_detect(self):
        class _Dummy(Interaction):
            pass
        with pytest.raises(TypeError,
                           match="Can't instantiate abstract class _Dummy"):
            _Dummy()

    @pytest.mark.parametrize("index", [
        0, 1, 3, 42, 78
    ])
    def test_get_mapindex(self, index):
        parent_index = get_mapindex(ligand_mol[0], index)
        assert parent_index == index

    def test_vdwcontact_tolerance_error(self):
        with pytest.raises(ValueError,
                           match="`tolerance` must be 0 or positive"):
            VdWContact(tolerance=-1)

    @pytest.mark.parametrize("lig_mol, prot_mol", [
        ("benzene", "cation")
    ], indirect=["lig_mol", "prot_mol"])
    def test_vdwcontact_cache(self, lig_mol, prot_mol):
        vdw = VdWContact()
        assert vdw._vdw_cache == {}
        vdw.detect(lig_mol, prot_mol)
        for (lig, res), value in vdw._vdw_cache.items():
            vdw_dist = vdwradii[lig] + vdwradii[res] + vdw.tolerance
            assert vdw_dist == value

    @pytest.mark.parametrize(["interaction_qmol", "smiles", "expected"], [
        ("Hydrophobic.lig_pattern", "C", 1),
        ("Hydrophobic.lig_pattern", "O", 0),
        ("_BaseHBond.donor", "[OH2]", 2),
        ("_BaseHBond.donor", "[NH3]", 3),
        ("_BaseHBond.donor", "[SH2]", 2),
        ("_BaseHBond.donor", "O=C=O", 0),
        ("_BaseHBond.donor", "c1c[nH+]ccc1", 1),
        ("_BaseHBond.donor", "c1c[sH]ccc1", 1),
        ("_BaseHBond.acceptor", "O", 1),
        ("_BaseHBond.acceptor", "N", 1),
        ("_BaseHBond.acceptor", "[NH+]", 0),
        ("_BaseHBond.acceptor", "N-C=O", 1),
        ("_BaseHBond.acceptor", "N-C=[SH2]", 0),
        ("_BaseHBond.acceptor", "[nH+]1ccccc1", 0),
        ("_BaseHBond.acceptor", "n1ccccc1", 1),
        ("_BaseHBond.acceptor", "Nc1ccccc1", 0),
        ("_BaseHBond.acceptor", "o1cccc1", 0),
        ("_BaseHBond.acceptor", "COC=O", 1),
        ("_BaseXBond.donor", "CCl", 1),
        ("_BaseXBond.donor", "c1ccccc1Cl", 1),
        ("_BaseXBond.donor", "NCl", 1),
        ("_BaseXBond.donor", "c1cccc[n+]1Cl", 1),
        ("_BaseXBond.acceptor", "[NH3]", 3),
        ("_BaseXBond.acceptor", "[NH+]C", 0),
        ("_BaseXBond.acceptor", "c1ccccc1", 12),
        ("Cationic.lig_pattern", "[NH4+]", 1),
        ("Cationic.lig_pattern", "[Ca+2]", 1),
        ("Cationic.prot_pattern", "[Cl-]", 1),
        ("Cationic.prot_pattern", "C(=O)[O-]", 1),
        ("_BaseCationPi.cation", "[NH4+]", 1),
        ("_BaseCationPi.pi_ring", "c1ccccc1", 1),
        ("_BaseCationPi.pi_ring", "c1cocc1", 1),
        ("PiStacking.pi_ring", "c1ccccc1", 1),
        ("PiStacking.pi_ring", "c1cocc1", 1),
        ("_BaseMetallic.lig_pattern", "[Mg]", 1),
        ("_BaseMetallic.prot_pattern", "O", 1),
        ("_BaseMetallic.prot_pattern", "N", 1),
        ("_BaseMetallic.prot_pattern", "[NH+]", 0),
        ("_BaseMetallic.prot_pattern", "N-C=[SH2]", 0),
        ("_BaseMetallic.prot_pattern", "[nH+]1ccccc1", 0),
        ("_BaseMetallic.prot_pattern", "Nc1ccccc1", 0),
        ("_BaseMetallic.prot_pattern", "o1cccc1", 0),
        ("_BaseMetallic.prot_pattern", "COC=O", 2),
    ], indirect=["interaction_qmol"])
    def test_smarts_matches(self, interaction_qmol, smiles, expected):
        mol = Chem.MolFromSmiles(smiles)
        mol = Chem.AddHs(mol)
        if isinstance(interaction_qmol, list):
            n_matches = sum(len(mol.GetSubstructMatches(qmol))
                            for qmol in interaction_qmol)
        else:
            n_matches = len(mol.GetSubstructMatches(interaction_qmol))
        assert n_matches == expected
