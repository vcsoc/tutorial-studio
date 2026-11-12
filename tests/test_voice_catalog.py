import pytest

from tutorial_studio.assets import DEFAULT_MODELS
from tutorial_studio.gallery import page_html
from tutorial_studio.voices import BY_ID, CATALOG, VOICES


def test_shared_catalog_has_samples_and_expected_locales():
    assert len(CATALOG) == len(BY_ID) == len(VOICES) == 23
    assert {v["locale"] for v in CATALOG} == {"United Kingdom", "United States", "France", "Spain", "Italy", "Brazil", "India"}
    assert sum(v["language"] == "English" for v in CATALOG) == 15
    assert all(v["sample"] and VOICES[v["id"]][2] == v["lang"] for v in CATALOG)
    assert BY_ID["ff_siwis"]["sample"].startswith("Bienvenue")
    assert BY_ID["im_nicola"]["sample"] == BY_ID["if_sara"]["sample"]


@pytest.mark.skipif(not (DEFAULT_MODELS / "voices.bin").exists(), reason="Approved voice pack not installed")
def test_all_catalog_voices_exist_in_real_local_voice_pack():
    import numpy as np
    with np.load(DEFAULT_MODELS / "voices.bin", allow_pickle=False) as pack:
        assert set(BY_ID) <= set(pack.files)


def test_gallery_escapes_labels_and_samples():
    voice = {**CATALOG[0], "name": '<script>bad()</script>', "sample": '<img onerror="bad()">', "file": "safe.wav", "duration": 12.5}
    output = page_html([voice])
    assert '<script>bad()</script>' not in output
    assert '&lt;script&gt;' in output and '&lt;img' in output
    assert 'safe.wav' in output
