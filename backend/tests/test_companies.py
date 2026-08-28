import pytest

from jobping import registry
from jobping.companies import ALL, BY_KEY, SAMSUNG, SK, resolve, slugify


class TestRegistryIntegrity:
    def test_keys_are_unique(self):
        keys = [c.key for c in ALL]
        assert len(keys) == len(set(keys))

    def test_every_company_belongs_to_a_real_adapter(self):
        sources = set(registry.ADAPTERS)
        assert {c.source for c in ALL} <= sources

    def test_display_names_are_unique_within_a_source(self):
        """앱의 회사 선택 화면에 같은 이름이 두 번 뜨면 고를 수가 없다."""
        for source in {c.source for c in ALL}:
            names = [c.display_name for c in ALL if c.source == source]
            assert len(names) == len(set(names))


class TestResolve:
    def test_samsung_resolves_by_filter_code(self):
        assert resolve("samsung", "C10CAH") == "samsung_ds"

    def test_samsung_resolves_by_display_name(self):
        """목록 HTML은 코드가 아니라 회사명을 준다."""
        assert resolve("samsung", "삼성전자 DS부문") == "samsung_ds"

    @pytest.mark.parametrize("name", ["SK하이닉스", "SK hynix"])
    def test_sk_resolves_in_both_locales(self, name):
        """SK 포털은 Accept-Language 에 따라 회사명 표기를 바꾼다."""
        assert resolve("skcareers", name) == "sk_hynix"

    @pytest.mark.parametrize("name", ["SK케미칼(LS)", "SK케미칼(GC)", "SK chemicals(LS)"])
    def test_business_unit_suffix_is_trimmed(self, name):
        assert resolve("skcareers", name) == "sk_chemicals"

    def test_same_code_in_different_sources_does_not_collide(self):
        assert resolve("samsung", "SK하이닉스") != resolve("skcareers", "SK하이닉스")

    def test_unknown_subsidiary_falls_back_to_a_slug(self):
        """그룹이 계열사를 추가했다고 수집이 멈추면 안 된다."""
        key = resolve("skcareers", "SK신규회사")
        assert key == "sk신규회사"
        assert key not in BY_KEY  # 앱 목록에는 노출되지 않는다

    def test_blank_input_still_yields_a_key(self):
        assert resolve("samsung", "") == "samsung_unknown"


class TestSlugify:
    @pytest.mark.parametrize("raw,expected", [
        ("SK inc.(AX)", "sk_inc_ax"),
        ("엔솔브(주)", "엔솔브_주"),
        ("  Tmap  Mobility ", "tmap_mobility"),
    ])
    def test_produces_stable_keys(self, raw, expected):
        assert slugify(raw) == expected


class TestCoverage:
    def test_group_portals_cover_many_subsidiaries(self):
        """어댑터 하나가 계열사 수십 곳을 내보낸다는 게 이 구조의 핵심이다."""
        assert len(SAMSUNG) > 20
        assert len(SK) > 20

    def test_app_only_offers_companies_from_verified_sources(self):
        verified = {a.key for a in registry.verified_adapters()}
        assert {c.source for c in registry.app_companies()} <= verified
