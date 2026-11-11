from datetime import date
from types import SimpleNamespace

from django.test import SimpleTestCase

from . import confidence

TODAY = date(2026, 11, 10)

# Toy 3-d "embeddings": each axis is a topic
GIFT_CARDS, URGENCY, WEATHER = [1, 0, 0], [0, 1, 0], [0, 0, 1]
VECTORS = {"gift": GIFT_CARDS, "urgent": URGENCY, "weather": WEATHER}


def fake_embed(texts):
    return [next(v for k, v in VECTORS.items() if k in t.lower()) for t in texts]


def hit(source_id, url, vector, score=0.75, publisher="Pub", reviewed=TODAY, words=80):
    source = SimpleNamespace(url=url, publisher=publisher, last_reviewed=reviewed, last_ingested=None)
    chunk = SimpleNamespace(source_id=source_id, source=source, embedding=vector,
                            text=" ".join(["word"] * words))
    return chunk, score


ANSWER = """Warning signs I notice:
- Asking for gift cards is a scam sign [1].
- Urgent pressure to pay now is a red flag [2].
What to do next:
- Hang up and call a number you trust about the gift card request [1]."""


class ParsingTests(SimpleTestCase):
    def test_cited_numbers_handles_grouped_citations(self):
        self.assertEqual(confidence.cited_numbers("a [1] b [2, 3] c [4][5]"), {1, 2, 3, 4, 5})

    def test_split_agreement_strips_line(self):
        text, label = confidence.split_agreement("- point [1]\nSource check: Conflict")
        self.assertEqual(text, "- point [1]")
        self.assertEqual(label, "conflict")

    def test_extract_claims_uses_bullets(self):
        claims = confidence.extract_claims(ANSWER)
        self.assertEqual(len(claims), 3)
        self.assertEqual(claims[1], ("Urgent pressure to pay now is a red flag.", {2}))


class ReliabilityTests(SimpleTestCase):
    def test_government_outranks_unknown_site(self):
        gov, _ = hit(1, "https://www.consumerfinance.gov/a", GIFT_CARDS)
        blog, _ = hit(2, "https://scamtips.example.com/a", GIFT_CARDS)
        g, label, _ = confidence.source_reliability(gov.source, "q", gov.text, TODAY)
        b, _, _ = confidence.source_reliability(blog.source, "q", blog.text, TODAY)
        self.assertEqual(label, "Official government source")
        self.assertGreater(g, b)

    def test_stale_and_archived_pages_lose_reliability(self):
        fresh, _ = hit(1, "https://www.consumerfinance.gov/a", GIFT_CARDS)
        old, _ = hit(2, "https://www.consumerfinance.gov/archive/a", GIFT_CARDS, reviewed=date(2021, 1, 1))
        f, _, _ = confidence.source_reliability(fresh.source, "q", fresh.text, TODAY)
        o, _, notes = confidence.source_reliability(old.source, "q", old.text, TODAY)
        self.assertLess(o, f)
        self.assertTrue(any("archived" in n for n in notes))

    def test_primary_authority_bonus(self):
        ncoa, _ = hit(1, "https://www.ncoa.org/a", GIFT_CARDS)
        irs, _ = hit(2, "https://www.irs.gov/a", GIFT_CARDS)
        _, _, notes = confidence.source_reliability(irs.source, "Is this IRS tax call real?", irs.text, TODAY)
        self.assertIn("primary authority on this topic", notes)
        n, _, _ = confidence.source_reliability(ncoa.source, "Is this IRS tax call real?", ncoa.text, TODAY)
        self.assertLess(n, 1.0)


class AssessTests(SimpleTestCase):
    def assess(self, hits, answer=ANSWER, agreement="agree"):
        return confidence.assess("gift card call", answer, hits, fake_embed, agreement, TODAY)

    def test_no_hits_is_unrated(self):
        conf, details = self.assess([])
        self.assertEqual(conf["level"], "none")
        self.assertEqual(details, [])

    def test_well_supported_answer_scores_high(self):
        conf, details = self.assess([
            hit(1, "https://www.consumerfinance.gov/a", GIFT_CARDS, publisher="CFPB"),
            hit(2, "https://www.ncoa.org/b", URGENCY, publisher="NCOA"),
        ])
        self.assertEqual(conf["level"], "high")
        self.assertTrue(all(d["supports"] for d in details))
        self.assertEqual(conf["factors"]["quantity"]["count"], 2)
        self.assertEqual(conf["factors"]["quantity"]["detail"], "CFPB, NCOA.")

    def test_more_unrelated_sources_do_not_raise_score(self):
        base = [hit(1, "https://www.consumerfinance.gov/a", GIFT_CARDS),
                hit(2, "https://www.ncoa.org/b", URGENCY)]
        padded = base + [hit(3, "https://www.weather.gov/c", WEATHER),
                         hit(4, "https://www.noaa.gov/d", WEATHER)]
        self.assertEqual(self.assess(base)[0]["score"], self.assess(padded)[0]["score"])

    def test_same_publisher_counts_less_than_independent(self):
        same = [hit(1, "https://www.consumerfinance.gov/a", GIFT_CARDS),
                hit(2, "https://www.consumerfinance.gov/b", URGENCY)]
        independent = [hit(1, "https://www.consumerfinance.gov/a", GIFT_CARDS),
                       hit(2, "https://www.ftc.gov/b", URGENCY)]
        conf_same, conf_ind = self.assess(same)[0], self.assess(independent)[0]
        self.assertEqual(conf_same["factors"]["quantity"]["count"], 1)
        self.assertEqual(conf_ind["factors"]["quantity"]["count"], 2)
        self.assertLess(conf_same["score"], conf_ind["score"])

    def test_conflict_is_capped(self):
        hits = [hit(1, "https://www.consumerfinance.gov/a", GIFT_CARDS),
                hit(2, "https://www.ncoa.org/b", URGENCY)]
        conf, _ = self.assess(hits, agreement="conflict")
        self.assertLessEqual(conf["score"], confidence.CONFLICT_CAP)
        self.assertNotEqual(conf["level"], "high")

    def test_citing_the_wrong_passage_scores_low(self):
        hits = [hit(1, "https://www.weather.gov/a", WEATHER),
                hit(2, "https://www.noaa.gov/b", WEATHER)]
        conf, details = self.assess(hits)
        self.assertEqual(conf["level"], "low")
        self.assertLessEqual(conf["score"], confidence.NO_GROUNDING_CAP)
        self.assertFalse(any(d["supports"] for d in details))

    def test_uncited_claims_reduce_relevance(self):
        hits = [hit(1, "https://www.consumerfinance.gov/a", GIFT_CARDS),
                hit(2, "https://www.ncoa.org/b", URGENCY)]
        uncited = ANSWER.replace(" [2]", "")
        full = self.assess(hits)[0]["factors"]["relevance"]["score"]
        partial_conf = self.assess(hits, answer=uncited)[0]
        self.assertLess(partial_conf["factors"]["relevance"]["score"], full)
